"""
FilterAgent — Deduplicates opportunities against database history and removes dismissed items.
"""

from typing import Dict, Any, List
from .base_agent import BaseAgent
from ..database import get_db


class FilterAgent(BaseAgent):
    """Filters out duplicate and previously dismissed opportunities."""

    def __init__(self):
        super().__init__(
            name="FilterAgent",
            description="Deduplicates and filters opportunities against history"
        )

    def get_system_prompt(self) -> str:
        return "You are a deduplication filter. Not used for Claude calls."

    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Filter out duplicates and low-score items."""
        opportunities = input_data.get('opportunities', [])

        if not opportunities:
            return {'filtered_opportunities': []}

        self.log(f"Filtering {len(opportunities)} opportunities...")

        # Get existing titles and URLs from database
        conn = get_db()
        existing_titles = set()
        existing_urls = set()
        dismissed_ids = set()

        for row in conn.execute("SELECT title, url FROM opportunities").fetchall():
            existing_titles.add(row['title'].lower().strip())
            if row['url']:
                existing_urls.add(row['url'].strip())

        for row in conn.execute("SELECT opportunity_id FROM dismissed").fetchall():
            dismissed_ids.add(row['opportunity_id'])

        conn.close()

        # Filter
        filtered = []
        seen_titles = set()

        for opp in opportunities:
            title = opp.get('title', '').strip()
            url = opp.get('url', '').strip()
            score = opp.get('score', 0)

            # Skip low scores
            if score < 4:
                continue

            # Skip duplicates within this batch
            title_lower = title.lower()
            if title_lower in seen_titles:
                continue
            seen_titles.add(title_lower)

            # Skip if already in database
            if title_lower in existing_titles:
                continue
            if url and url in existing_urls:
                continue

            filtered.append(opp)

        self.log(f"After filtering: {len(filtered)} opportunities (removed {len(opportunities) - len(filtered)})")
        return {'filtered_opportunities': filtered}
