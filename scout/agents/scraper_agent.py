"""
ScraperAgent — Fetches raw data from Product Hunt, Hacker News, Reddit, and Gumroad.
Uses RSS feeds and APIs (all free tier).
"""

import feedparser
import requests
from typing import Dict, Any, List
from datetime import datetime
from .base_agent import BaseAgent

# Optional: Reddit via PRAW (requires credentials)
try:
    import praw
    PRAW_AVAILABLE = True
except ImportError:
    PRAW_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False


class ScraperAgent(BaseAgent):
    """Scrapes opportunities from multiple free sources."""

    def __init__(self):
        super().__init__(
            name="ScraperAgent",
            description="Fetches raw data from Product Hunt, Hacker News, Reddit, and Gumroad"
        )
        self.sources = {
            'product_hunt': 'https://www.producthunt.com/feed',
            'hacker_news_best': 'https://hnrss.org/best',
            'hacker_news_show': 'https://hnrss.org/show',
        }
        self.reddit_subs = ['SaaS', 'smallbusiness', 'Entrepreneur', 'LocalLLaMA', 'artificial']

    def get_system_prompt(self) -> str:
        return "You are a data collection agent. Your job is to gather raw items from various sources."

    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Scrape all sources and return combined raw items."""
        self.log("Starting daily scrape...")
        all_items = []

        # RSS Feeds
        for source_name, url in self.sources.items():
            items = self._scrape_rss(source_name, url)
            all_items.extend(items)
            self.log(f"  {source_name}: {len(items)} items")

        # Reddit
        reddit_items = self._scrape_reddit()
        all_items.extend(reddit_items)
        self.log(f"  reddit: {len(reddit_items)} items")

        # Gumroad trending
        gumroad_items = self._scrape_gumroad()
        all_items.extend(gumroad_items)
        self.log(f"  gumroad: {len(gumroad_items)} items")

        self.log(f"Total raw items: {len(all_items)}")
        return {'raw_items': all_items, 'sources_scanned': list(self.sources.keys()) + ['reddit', 'gumroad']}

    def _scrape_rss(self, source: str, url: str) -> List[Dict]:
        """Parse an RSS feed into standardized items."""
        items = []
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:25]:  # Limit to 25 most recent
                items.append({
                    'title': entry.get('title', 'No title'),
                    'description': entry.get('summary', entry.get('description', '')),
                    'url': entry.get('link', ''),
                    'source': source,
                    'published': entry.get('published', ''),
                    'scraped_at': datetime.now().isoformat()
                })
        except Exception as e:
            self.log(f"RSS error for {source}: {e}")
        return items

    def _scrape_reddit(self) -> List[Dict]:
        """Scrape Reddit using PRAW if available, otherwise skip."""
        import os
        items = []

        if not PRAW_AVAILABLE:
            self.log("PRAW not available, skipping Reddit")
            return items

        client_id = os.environ.get('REDDIT_CLIENT_ID')
        client_secret = os.environ.get('REDDIT_CLIENT_SECRET')

        if not client_id or not client_secret:
            self.log("Reddit credentials not set, skipping Reddit")
            return items

        try:
            reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent='Scout Intelligence Agent v1.0'
            )

            for sub_name in self.reddit_subs:
                try:
                    subreddit = reddit.subreddit(sub_name)
                    for post in subreddit.hot(limit=10):
                        # Skip stickied posts
                        if post.stickied:
                            continue
                        items.append({
                            'title': post.title,
                            'description': post.selftext[:500] if post.selftext else '',
                            'url': f"https://reddit.com{post.permalink}",
                            'source': f"reddit_r/{sub_name}",
                            'published': datetime.fromtimestamp(post.created_utc).isoformat(),
                            'score': post.score,
                            'num_comments': post.num_comments,
                            'scraped_at': datetime.now().isoformat()
                        })
                except Exception as e:
                    self.log(f"Reddit r/{sub_name} error: {e}")

        except Exception as e:
            self.log(f"Reddit connection error: {e}")

        return items

    def _scrape_gumroad(self) -> List[Dict]:
        """Scrape Gumroad discover page for trending products."""
        items = []
        if not BS4_AVAILABLE:
            self.log("BeautifulSoup not available, skipping Gumroad")
            return items

        try:
            headers = {'User-Agent': 'Scout Intelligence Agent v1.0'}
            resp = requests.get('https://gumroad.com/discover', headers=headers, timeout=15)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                # Look for product cards
                cards = soup.select('article, [class*="product"], [class*="card"]')
                for card in cards[:20]:
                    title_el = card.select_one('h2, h3, [class*="title"]')
                    desc_el = card.select_one('p, [class*="desc"], [class*="summary"]')
                    link_el = card.select_one('a[href]')

                    if title_el:
                        items.append({
                            'title': title_el.get_text(strip=True),
                            'description': desc_el.get_text(strip=True) if desc_el else '',
                            'url': link_el['href'] if link_el and link_el.get('href') else '',
                            'source': 'gumroad',
                            'scraped_at': datetime.now().isoformat()
                        })
            else:
                self.log(f"Gumroad returned status {resp.status_code}")
        except Exception as e:
            self.log(f"Gumroad scraping error: {e}")

        return items
