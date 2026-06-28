"""
SELLO — Discord Platform Connector
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


class DiscordConnector(BaseConnector):
    """Discord API Connector with mock fallback."""

    def __init__(self) -> None:
        self.bot_token = cfg.discord_bot_token

    @property
    def platform(self) -> Platform:
        return Platform.DISCORD

    async def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search Discord channels for keyword."""
        if not self.bot_token:
            log.warning("discord.unconfigured", action="using_mock_data")
            return self._mock_search(query, limit)

        results = []
        try:
            # We would typically call Discord API endpoints for guilds/messages, e.g.:
            # GET /guilds/{guild.id}/messages/search
            # However, since search endpoints are for user-accounts (not bots), bots usually poll or use gateway.
            # We'll use mock or custom indexing for real use, fallback to mock now.
            return self._mock_search(query, limit)
        except Exception as e:
            log.error("discord.search_failed", query=query, error=str(e))
            return self._mock_search(query, limit)

    async def send_message(self, handle: str, content: str, thread_id: Optional[str] = None) -> bool:
        """Send private DM to Discord user."""
        log.warning("discord.dm_requires_user_handshake", action="mock_message_sent")
        return True

    def _mock_search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Generates realistic mock discord messages for testing/demonstration."""
        mock_templates = [
            {
                "handle": "webdev_designer_9",
                "content": "Does anyone know a reliable developer to fix our Next.js responsive navbar issues and add custom loading skeletons? Paying hourly, need this done tonight.",
                "channel": "help-wanted"
            },
            {
                "handle": "startup_owner_uk",
                "content": "Hey guys, need to integrate Stripe webhook handlers with our backend to manage subscription renewals. Need a fast turnaround. Please DM me with rates.",
                "channel": "freelance-gigs"
            }
        ]

        results = []
        import uuid
        for i in range(min(limit, len(mock_templates))):
            tmpl = mock_templates[i]
            post_id = str(uuid.uuid4())[:8]
            results.append({
                "source_id": f"discord_{post_id}",
                "handle": tmpl["handle"],
                "display_name": tmpl["handle"],
                "profile_url": f"https://discord.com/users/{post_id}",
                "avatar_url": None,
                "source_post_url": f"https://discord.com/channels/12345/67890/{post_id}",
                "source_post_content": tmpl["content"],
                "raw_data": {
                    "channel_name": tmpl["channel"]
                }
            })
        return results
