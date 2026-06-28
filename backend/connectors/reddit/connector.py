"""
SELLO — Reddit Platform Connector
"""

from __future__ import annotations

import praw
import structlog
from typing import Any, Optional
from database.models import Platform
from connectors.base import BaseConnector
from core.config import get_settings

log = structlog.get_logger(__name__)
cfg = get_settings()


class RedditConnector(BaseConnector):
    """Reddit API Connector using PRAW, with sandbox/mock fallback."""

    def __init__(self) -> None:
        self.reddit: Optional[praw.Reddit] = None
        if cfg.reddit_client_id and cfg.reddit_client_secret:
            try:
                self.reddit = praw.Reddit(
                    client_id=cfg.reddit_client_id,
                    client_secret=cfg.reddit_client_secret,
                    user_agent=cfg.reddit_user_agent,
                )
                log.info("reddit.connected")
            except Exception as e:
                log.error("reddit.init_failed", error=str(e))

    @property
    def platform(self) -> Platform:
        return Platform.REDDIT

    async def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search subreddits or global reddit search for keyword."""
        if not self.reddit:
            log.warning("reddit.unconfigured", action="using_mock_data")
            return self._mock_search(query, limit)

        results = []
        try:
            # PRAW search is blocking, run in executor if needed, but since it's simple:
            submissions = self.reddit.subreddit("all").search(query, limit=limit)
            for submission in submissions:
                results.append({
                    "source_id": f"reddit_{submission.id}",
                    "handle": submission.author.name if submission.author else "deleted",
                    "display_name": submission.author.name if submission.author else "deleted",
                    "profile_url": f"https://reddit.com/user/{submission.author.name}" if submission.author else "",
                    "avatar_url": None,
                    "source_post_url": f"https://reddit.com{submission.permalink}",
                    "source_post_content": f"{submission.title}\n\n{submission.selftext}",
                    "raw_data": {
                        "score": submission.score,
                        "num_comments": submission.num_comments,
                        "subreddit": submission.subreddit.display_name,
                    }
                })
        except Exception as e:
            log.error("reddit.search_failed", query=query, error=str(e))
            return self._mock_search(query, limit)

        return results

    async def send_message(self, handle: str, content: str, thread_id: Optional[str] = None) -> bool:
        """Send private message to user."""
        if not self.reddit:
            log.warning("reddit.unconfigured", action="mock_message_sent")
            return True

        try:
            redditor = self.reddit.redditor(handle)
            redditor.message(subject="Inquiry regarding your post", message=content)
            log.info("reddit.message_sent", to=handle)
            return True
        except Exception as e:
            log.error("reddit.message_failed", to=handle, error=str(e))
            return False

    def _mock_search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Generates realistic mock leads for testing/demonstration."""
        mock_templates = [
            {
                "handle": "tech_founder_99",
                "title": "Looking for a software agency to build our SaaS MVP",
                "text": "Hey everyone, we recently raised a small pre-seed round and want to outsource the first version of our B2B SaaS dashboard. It needs to have React frontend, FastAPI backend, and integrate with Stripe. Anyone have recommendations? Budget is around $15k.",
                "subreddit": "reactjs"
            },
            {
                "handle": "marketing_director",
                "title": "Need custom scrapers / data pipelines built",
                "text": "We need to scrape leads from public directories and sync them to our CRM. Looking for a Python/Node developer who can build this in a couple of weeks. Budget: $3,000.",
                "subreddit": "Python"
            },
            {
                "handle": "ecom_guy_la",
                "title": "Need a high-converting landing page for Shopify brand",
                "text": "Our current landing page has terrible conversion rates. Need a designer/developer who knows conversion rate optimization (CRO) and custom Shopify development. Drop portfolios.",
                "subreddit": "shopify"
            },
            {
                "handle": "sme_owner_london",
                "title": "Our WordPress site got hacked, need urgent fix and rebuild",
                "text": "Title says it all. Our company website got infected with malware. We want to completely scrap WordPress and migrate to a static Webflow or Next.js page. Please DM if you can start immediately.",
                "subreddit": "webdev"
            }
        ]

        results = []
        import uuid
        for i in range(min(limit, len(mock_templates))):
            tmpl = mock_templates[i]
            post_id = str(uuid.uuid4())[:8]
            results.append({
                "source_id": f"reddit_{post_id}",
                "handle": tmpl["handle"],
                "display_name": f"/u/{tmpl['handle']}",
                "profile_url": f"https://reddit.com/user/{tmpl['handle']}",
                "avatar_url": None,
                "source_post_url": f"https://reddit.com/r/{tmpl['subreddit']}/comments/{post_id}",
                "source_post_content": f"{tmpl['title']}\n\n{tmpl['text']}",
                "raw_data": {
                    "score": 42 + i,
                    "num_comments": 12,
                    "subreddit": tmpl["subreddit"],
                }
            })
        return results
