"""
SELLO — Platform Connectors Registry
"""

from __future__ import annotations

from typing import list, dict
from database.models import Platform
from connectors.base import BaseConnector
from connectors.reddit.connector import RedditConnector
from connectors.twitter.connector import TwitterConnector
from connectors.github.connector import GitHubConnector
from connectors.discord.connector import DiscordConnector

_connectors: dict[Platform, BaseConnector] = {
    Platform.REDDIT: RedditConnector(),
    Platform.TWITTER: TwitterConnector(),
    Platform.GITHUB: GitHubConnector(),
    Platform.DISCORD: DiscordConnector(),
}


def get_connector(platform: Platform) -> BaseConnector:
    """Retrieve the registered connector instance for a platform."""
    connector = _connectors.get(platform)
    if not connector:
        raise ValueError(f"No connector registered for platform: {platform}")
    return connector


def get_all_connectors() -> list[BaseConnector]:
    """Retrieve all registered connectors."""
    return list(_connectors.values())
