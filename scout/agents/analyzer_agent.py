"""
AnalyzerAgent — Uses Claude to detect opportunities, score them, and categorize by domain.
This is the brain of Scout.
"""

import json
from typing import Dict, Any, List
from .base_agent import BaseAgent


class AnalyzerAgent(BaseAgent):
    """Analyzes raw scraped items to detect market gaps and opportunities."""

    def __init__(self):
        super().__init__(
            name="AnalyzerAgent",
            description="Uses Claude to detect and score opportunities from raw data"
        )
        self.max_tokens = 4000

    def get_system_prompt(self) -> str:
        return """You are Scout's Opportunity Analyzer — an elite market intelligence agent specialized in the AGENTIC WEB.

CONTEXT: The "agentic web" is the next evolution of the internet — where AI agents autonomously browse, act, and transact on behalf of users. Key protocols include Anthropic's MCP (Model Context Protocol) and Google's A2A (Agent-to-Agent). Agentic browsers like OpenAI Atlas and Chrome auto-browse are deploying to billions. Gartner predicts 40% of enterprise apps will embed AI agents by end of 2026. This is a massive emerging market.

Your job: Take raw items scraped from Product Hunt, Hacker News, Reddit, and Gumroad,
and identify ACTIONABLE opportunities for a solo developer to build AGENTIC WEB products and services.

You evaluate across these domains:
1. AGENT TOOLS — MCP servers, agent-to-agent protocols, agent SDKs, browser automation tools, orchestration frameworks. Look for gaps: what tools do agent builders need that don't exist yet?
2. AGENT SERVICES — Businesses that need agent-friendly APIs, websites that need agent-readable structured data, agent-as-a-service products. What services could be built where AI agents are the customer?
3. AGENT INFRASTRUCTURE — Monitoring, security, testing, deployment tools for agents. What does the "DevOps for agents" stack look like? What's missing?
4. AGENT-POWERED PRODUCTS — End-user products powered by autonomous agents: personal shopping agents, research agents, scheduling agents, data gathering agents, outreach agents. What agent-powered products are people asking for?

For each opportunity you identify, provide:
- title: Clear, concise opportunity name
- description: 2-3 sentence explanation of the opportunity and why it's viable in the agentic web context
- score: 1-10 rating (10 = highest potential). Score based on:
  * Revenue potential (can this make $500+/mo?)
  * Feasibility (can one person build this in 1-2 weeks with AI assistance?)
  * Demand signal (are people actively asking for this? Is the agentic web trend creating this need?)
  * Competition (is the market underserved? Is this a new category?)
  * Timing (is this riding the agentic web wave? Will demand grow?)
- domain: One of "agent_tools", "agent_services", "agent_infra", or "agent_products"
- tags: Comma-separated relevant tags
- source_item: The title of the raw item that sparked this insight

THINKING FRAMEWORK:
- When you see a new AI product launch → ask "what agent tooling does this create demand for?"
- When you see a complaint about AI limitations → ask "could an agent solve this?"
- When you see enterprise AI adoption → ask "what infrastructure is missing for agents at scale?"
- When you see a manual workflow people hate → ask "could an autonomous agent handle this end-to-end?"
- When you see MCP, A2A, or agent protocol mentions → ask "what's the business opportunity around this?"
- Pay special attention to: MCP servers people wish existed, agent orchestration pain points, agent security/monitoring gaps, agent-friendly API wrappers for legacy services

IMPORTANT:
- Not every raw item is an opportunity. Many will be noise. Be selective but creative.
- Think like a product strategist for the agentic web era.
- Score honestly. Most items should be 3-6. Reserve 8+ for exceptional finds with clear demand signals.
- Prefer opportunities a SOLO DEVELOPER can build and ship, not giant enterprise plays.

Return your analysis as a JSON array of opportunity objects. If no opportunities found, return [].
"""

    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze raw items and return scored opportunities."""
        raw_items = input_data.get('raw_items', [])

        if not raw_items:
            self.log("No raw items to analyze")
            return {'opportunities': []}

        # Process in batches to stay within token limits
        batch_size = 30
        all_opportunities = []

        for i in range(0, len(raw_items), batch_size):
            batch = raw_items[i:i + batch_size]
            self.log(f"Analyzing batch {i // batch_size + 1} ({len(batch)} items)...")

            opportunities = self._analyze_batch(batch)
            all_opportunities.extend(opportunities)

        self.log(f"Found {len(all_opportunities)} opportunities from {len(raw_items)} raw items")
        return {'opportunities': all_opportunities}

    def _analyze_batch(self, items: List[Dict]) -> List[Dict]:
        """Send a batch of items to Claude for analysis."""
        # Prepare items summary for Claude
        items_text = ""
        for idx, item in enumerate(items, 1):
            items_text += f"\n--- Item {idx} ---\n"
            items_text += f"Source: {item.get('source', 'unknown')}\n"
            items_text += f"Title: {item.get('title', 'No title')}\n"
            desc = item.get('description', '')
            if desc:
                items_text += f"Description: {desc[:300]}\n"
            if item.get('score'):
                items_text += f"Upvotes: {item['score']}\n"
            if item.get('num_comments'):
                items_text += f"Comments: {item['num_comments']}\n"

        prompt = f"""Analyze these {len(items)} items scraped today and identify actionable opportunities.

{items_text}

Return ONLY a valid JSON array of opportunity objects. Each object must have:
title, description, score (1-10), domain, tags, source_item

If no real opportunities found, return: []"""

        response = self.call_claude([{"role": "user", "content": prompt}])

        # Parse JSON from response
        try:
            # Try to extract JSON from the response
            text = response.strip()
            # Handle markdown code blocks
            if '```json' in text:
                text = text.split('```json')[1].split('```')[0].strip()
            elif '```' in text:
                text = text.split('```')[1].split('```')[0].strip()

            opportunities = json.loads(text)
            if not isinstance(opportunities, list):
                opportunities = []

            # Validate and clean each opportunity
            cleaned = []
            for opp in opportunities:
                if isinstance(opp, dict) and 'title' in opp:
                    cleaned.append({
                        'title': str(opp.get('title', '')),
                        'description': str(opp.get('description', '')),
                        'score': float(opp.get('score', 0)),
                        'domain': str(opp.get('domain', 'unknown')),
                        'tags': str(opp.get('tags', '')),
                        'source': str(opp.get('source_item', '')),
                        'url': str(opp.get('url', '')),
                    })
            return cleaned

        except (json.JSONDecodeError, IndexError, ValueError) as e:
            self.log(f"Failed to parse Claude response: {e}")
            self.log(f"Response was: {response[:200]}")
            return []
