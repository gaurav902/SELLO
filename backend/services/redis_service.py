"""
SELLO — Redis Cache & Messaging Service
"""

from __future__ import annotations

import json
import structlog
from typing import Any, Optional
from redis.asyncio import Redis, from_url
from core.config import get_settings

log = structlog.get_logger(__name__)
cfg = get_settings()


class RedisService:
    """Interacts with Redis for caching, state management, and pub/sub."""

    def __init__(self) -> None:
        self.redis: Optional[Redis] = None

    async def get_client(self) -> Redis:
        """Get or initialize Redis connection."""
        if self.redis is None:
            self.redis = from_url(cfg.redis_url, decode_responses=True)
            log.info("redis.connected")
        return self.redis

    async def set_cache(self, key: str, value: Any, expire_seconds: int = 3600) -> None:
        """Cache a JSON-serializable value."""
        try:
            client = await self.get_client()
            serialized = json.dumps(value)
            await client.set(key, serialized, ex=expire_seconds)
        except Exception as e:
            log.error("redis.set_cache_failed", key=key, error=str(e))

    async def get_cache(self, key: str) -> Optional[Any]:
        """Retrieve a cached value."""
        try:
            client = await self.get_client()
            val = await client.get(key)
            if val:
                return json.loads(val)
        except Exception as e:
            log.error("redis.get_cache_failed", key=key, error=str(e))
        return None

    async def delete_cache(self, key: str) -> None:
        """Delete a cached value."""
        try:
            client = await self.get_client()
            await client.delete(key)
        except Exception as e:
            log.error("redis.delete_cache_failed", key=key, error=str(e))

    async def publish(self, channel: str, message: dict[str, Any]) -> None:
        """Publish a message to Redis Pub/Sub."""
        try:
            client = await self.get_client()
            await client.publish(channel, json.dumps(message))
        except Exception as e:
            log.error("redis.publish_failed", channel=channel, error=str(e))

    async def close(self) -> None:
        """Dispose Redis connection."""
        if self.redis:
            await self.redis.close()
            self.redis = None
            log.info("redis.closed")


# Singleton instance
redis_service = RedisService()
