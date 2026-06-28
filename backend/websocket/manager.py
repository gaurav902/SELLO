"""
SELLO — WebSocket Manager
Broadcasts real-time agent events to connected frontend clients.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
import structlog

log = structlog.get_logger(__name__)


class ConnectionManager:
    """Manages all active WebSocket connections, grouped by user_id."""

    def __init__(self) -> None:
        # {user_id: {connection_id: WebSocket}}
        self._connections: dict[str, dict[str, WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str) -> str:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        conn_id = str(uuid.uuid4())
        if user_id not in self._connections:
            self._connections[user_id] = {}
        self._connections[user_id][conn_id] = websocket
        log.info("websocket.connected", user_id=user_id, conn_id=conn_id)
        return conn_id

    def disconnect(self, user_id: str, conn_id: str) -> None:
        """Remove a closed connection."""
        if user_id in self._connections:
            self._connections[user_id].pop(conn_id, None)
            if not self._connections[user_id]:
                del self._connections[user_id]
        log.info("websocket.disconnected", user_id=user_id, conn_id=conn_id)

    async def send_to_user(self, user_id: str, event: dict[str, Any]) -> None:
        """Send a JSON event to all connections for a specific user."""
        connections = self._connections.get(user_id, {})
        dead = []
        payload = json.dumps({**event, "timestamp": datetime.now(timezone.utc).isoformat()})
        for conn_id, ws in connections.items():
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(conn_id)
        for conn_id in dead:
            self.disconnect(user_id, conn_id)

    async def broadcast(self, event: dict[str, Any]) -> None:
        """Send an event to ALL connected clients (admin broadcasts)."""
        tasks = [
            self.send_to_user(user_id, event)
            for user_id in list(self._connections.keys())
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    @property
    def total_connections(self) -> int:
        return sum(len(v) for v in self._connections.values())


# Singleton instance
ws_manager = ConnectionManager()


def emit(user_id: str, event_type: str, data: dict[str, Any]) -> asyncio.Task:
    """
    Fire-and-forget helper for emitting events from agent code.
    Usage: emit(user_id, "lead_discovered", {"lead_id": ..., "handle": ...})
    """
    event = {"type": event_type, "data": data}
    return asyncio.create_task(ws_manager.send_to_user(user_id, event))
