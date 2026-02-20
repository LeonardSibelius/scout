"""
ScoutOrchestrator — Coordinates the daily intelligence pipeline.
Scrape → Analyze → Filter → Store → Email
"""

import time
from typing import Dict, Any
from datetime import datetime

from .agents.scraper_agent import ScraperAgent
from .agents.analyzer_agent import AnalyzerAgent
from .agents.filter_agent import FilterAgent
from .database import save_opportunities, get_top_opportunities, log_scan
from .email_service import send_daily_digest


class ScoutOrchestrator:
    """Runs the full Scout pipeline."""

    def __init__(self):
        self.scraper = ScraperAgent()
        self.analyzer = AnalyzerAgent()
        self.filter = FilterAgent()

    def run_daily_scan(self) -> Dict[str, Any]:
        """Execute the full scan pipeline."""
        start_time = time.time()
        print(f"\n{'='*60}")
        print(f"SCOUT DAILY SCAN — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")

        # Step 1: Scrape
        scrape_result = self.scraper.process({})
        raw_items = scrape_result.get('raw_items', [])
        sources = scrape_result.get('sources_scanned', [])

        if not raw_items:
            print("No items scraped. Aborting scan.")
            duration = time.time() - start_time
            log_scan(','.join(sources), 0, 0, duration)
            return {'status': 'no_data', 'items_found': 0}

        # Step 2: Analyze with Claude
        analysis_result = self.analyzer.process({'raw_items': raw_items})
        opportunities = analysis_result.get('opportunities', [])

        # Step 3: Filter duplicates
        filter_result = self.filter.process({'opportunities': opportunities})
        filtered = filter_result.get('filtered_opportunities', [])

        # Step 4: Store in database
        added = save_opportunities(filtered)

        # Step 5: Send email digest
        top = get_top_opportunities(limit=5)
        email_sent = False
        if top:
            email_sent = send_daily_digest(top)

        duration = time.time() - start_time

        # Log the scan
        log_scan(','.join(sources), len(raw_items), added, duration)

        result = {
            'status': 'complete',
            'items_scraped': len(raw_items),
            'opportunities_detected': len(opportunities),
            'after_filtering': len(filtered),
            'new_stored': added,
            'email_sent': email_sent,
            'duration_seconds': round(duration, 1),
            'top_opportunities': top[:3]  # Preview
        }

        print(f"\n{'='*60}")
        print(f"SCAN COMPLETE in {result['duration_seconds']}s")
        print(f"  Scraped: {result['items_scraped']} items")
        print(f"  Opportunities: {result['opportunities_detected']} detected → {result['after_filtering']} new → {result['new_stored']} stored")
        print(f"  Email: {'sent' if email_sent else 'not sent'}")
        print(f"{'='*60}\n")

        return result
