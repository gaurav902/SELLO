"""
SELLO — Base Platform Connector Interface
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from database.models import Platform


class BaseConnector(ABC):
    """Abstract base class for all platform connectors (plugins)."""

    @property
    @abstractmethod
    def platform(self) -> Platform:
        """Return the platform type."""
        pass

    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """
        Search public posts / threads on this platform for keywords.
        Returns a list of dictionaries with standard keys:
            - source_id: str (unique post ID)
            - handle: str
            - display_name: str
            - profile_url: str
            - avatar_url: Optional[str]
            - source_post_url: str
            - source_post_content: str
            - raw_data: dict
        """
        pass

    @abstractmethod
    async def send_message(self, handle: str, content: str, thread_id: Optional[str] = None) -> bool:
        """
        Send a direct message or response to a lead.
        Returns True if successful, False otherwise.
        """
        pass
