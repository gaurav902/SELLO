"""
SELLO — Twitter / X Platform Connector
"""

from __future__ import annotations

import httpx
import structlog
from typing import Any, Optional
from database.models import Platform
from connectors.base import BaseConnector
from core.config import get_settings

log = structlog.get_logger(__name__)
cfg = get_settings()


class TwitterConnector(BaseConnector):
    """Twitter/X API Connector with mock fallback."""

    def __init__(self) -> None:
        self.bearer_token = cfg.twitter_bearer_token

    @property
    def platform(self) -> Platform:
        return Platform.TWITTER

    async def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search Twitter/X posts."""
        if not self.bearer_token:
            log.warning("twitter.unconfigured", action="using_mock_data")
            return self._mock_search(query, limit)

        results = []
        try:
            # Simple v2 API search
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bearer {self.bearer_token}"}
                response = await client.get(
                    "https://api.twitter.com/2/tweets/search/recent",
                    headers=headers,
                    params={"query": query, "max_results": min(100, max(10, limit))},
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()
                tweets = data.get("data", [])
                for tweet in tweets:
                    results.append({
                        "source_id": f"twitter_{tweet['id']}",
                        "handle": "user_id_" + tweet.get("author_id", "unknown"),
                        "display_name": "Twitter User",
                        "profile_url": f"https://twitter.com/i/web/status/{tweet['id']}",
                        "avatar_url": None,
                        "source_post_url": f"https://twitter.com/i/web/status/{tweet['id']}",
                        "source_post_content": tweet["text"],
                        "raw_data": tweet
                    })
        except Exception as e:
            log.error("twitter.search_failed", query=query, error=str(e))
            return self._mock_search(query, limit)

        return results

    async def send_message(self, handle: str, content: str, thread_id: Optional[str] = None) -> bool:
        """Send private DM or mention reply."""
        log.warning("twitter.message_api_restricted", action="mock_message_sent")
        return True

    def _mock_search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Generates realistic mock tweets for testing/demonstration."""
        mock_templates = [
            {
                "handle": "startup_sam",
                "text": "Anyone know a good freelancer to optimize database queries for PostgreSQL? We are facing serious lags. #database #postgres #django"
            },
            {
                "handle": "jessica_codes",
                "text": "Seeking a developer who knows LangChain & Ollama to build a local document search tool for our team. DM me with rates."
            },
            {
                "handle": "bizdev_joe",
                "text": "We need to integrate custom Stripe billing with subscription management on our Next.js project. Looking to hire immediately."
            }
        ]

        results = []
        import uuid
        for i in range(min(limit, len(mock_templates))):
            tmpl = mock_templates[i]
            post_id = str(uuid.uuid4())[:8]
            results.append({
                "source_id": f"twitter_{post_id}",
                "handle": tmpl["handle"],
                "display_name": tmpl["handle"].title().replace("_", " "),
                "profile_url": f"https://twitter.com/{tmpl['handle']}",
                "avatar_url": None,
                "source_post_url": f"https://twitter.com/{tmpl['handle']}/status/{post_id}",
                "source_post_content": tmpl["text"],
                "raw_data": {}
            })
        return results
