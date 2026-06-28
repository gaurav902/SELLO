"""
SELLO — GitHub Platform Connector
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


class GitHubConnector(BaseConnector):
    """GitHub API Connector with mock fallback."""

    def __init__(self) -> None:
        self.token = cfg.github_token

    @property
    def platform(self) -> Platform:
        return Platform.GITHUB

    async def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search GitHub issues."""
        if not self.token:
            log.warning("github.unconfigured", action="using_mock_data")
            return self._mock_search(query, limit)

        results = []
        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"token {self.token}",
                    "Accept": "application/vnd.github.v3+json",
                }
                # Search issues and PRs
                response = await client.get(
                    "https://api.github.com/search/issues",
                    headers=headers,
                    params={"q": f"{query} is:issue is:open", "per_page": limit},
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()
                items = data.get("items", [])
                for item in items:
                    user = item.get("user", {})
                    results.append({
                        "source_id": f"github_{item['id']}",
                        "handle": user.get("login", "unknown"),
                        "display_name": user.get("login", "unknown"),
                        "profile_url": user.get("html_url", ""),
                        "avatar_url": user.get("avatar_url", None),
                        "source_post_url": item["html_url"],
                        "source_post_content": f"{item['title']}\n\n{item.get('body') or ''}",
                        "raw_data": item
                    })
        except Exception as e:
            log.error("github.search_failed", query=query, error=str(e))
            return self._mock_search(query, limit)

        return results

    async def send_message(self, handle: str, content: str, thread_id: Optional[str] = None) -> bool:
        """Post a comment or send message. Since GitHub lacks user-to-user DMs via API, mock it."""
        log.warning("github.dms_unsupported", action="mock_message_sent")
        return True

    def _mock_search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Generates realistic mock github issues for testing/demonstration."""
        mock_templates = [
            {
                "handle": "opensourcer_bob",
                "title": "Need help setting up a robust FastAPI backend architecture",
                "body": "Our open source project is growing. We need to decouple our monolithic API structure to use Repository Pattern and Dependency Injection. Looking for experienced Python developers to contribute or consult.",
                "url": "https://github.com/fastapi/fastapi/issues/9988"
            },
            {
                "handle": "ai_startup_co",
                "title": "Integration with Local LLMs (Ollama) in LangGraph pipeline",
                "body": "We need help defining custom LangGraph state channels that dynamically swap between Qwen 7B and Llama3 models depending on intent scoring. Pull requests welcome, or reach out to us at dev@aistartup.co.",
                "url": "https://github.com/langchain-ai/langgraph/issues/7711"
            }
        ]

        results = []
        import uuid
        for i in range(min(limit, len(mock_templates))):
            tmpl = mock_templates[i]
            post_id = str(uuid.uuid4())[:8]
            results.append({
                "source_id": f"github_{post_id}",
                "handle": tmpl["handle"],
                "display_name": tmpl["handle"],
                "profile_url": f"https://github.com/{tmpl['handle']}",
                "avatar_url": None,
                "source_post_url": tmpl["url"],
                "source_post_content": f"{tmpl['title']}\n\n{tmpl['body']}",
                "raw_data": {}
            })
        return results
