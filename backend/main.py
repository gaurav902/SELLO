"""
SELLO — FastAPI Application Entry Point
"""

from __future__ import annotations

import structlog
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import ORJSONResponse

from core.config import get_settings
from database.session import init_db, close_db
from websocket.manager import ws_manager
from auth.dependencies import decode_token

# Routers
from api.v1 import auth, leads, campaigns, settings as settings_router

log = structlog.get_logger(__name__)
cfg = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Startup / shutdown lifecycle."""
    log.info("sello.startup", env=cfg.app_env, model=cfg.ollama_default_model)
    await init_db()
    log.info("sello.db_ready")
    from scheduler.tasks import start_scheduler, stop_scheduler
    start_scheduler()
    yield
    stop_scheduler()
    await close_db()
    log.info("sello.shutdown")


# ── App Instance ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="SELLO API",
    description="AI Business Development Employee — Backend API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)

# ── Middleware ─────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


# ── API Routers ────────────────────────────────────────────────────────────────

API_PREFIX = f"/api/{cfg.api_version}"

app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(leads.router, prefix=API_PREFIX)
app.include_router(campaigns.router, prefix=API_PREFIX)
app.include_router(settings_router.router, prefix=API_PREFIX)


# ── Health Check ──────────────────────────────────────────────────────────────

@app.get("/api/health", tags=["System"])
async def health() -> dict:
    return {
        "status": "ok",
        "app": cfg.app_name,
        "env": cfg.app_env,
        "version": "1.0.0",
        "ws_connections": ws_manager.total_connections,
    }


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str) -> None:
    """
    Real-time event stream. Client connects after login.
    Broadcasts: lead_discovered, lead_scored, outreach_drafted, etc.
    """
    conn_id = await ws_manager.connect(websocket, user_id)
    try:
        await ws_manager.send_to_user(user_id, {
            "type": "connected",
            "data": {"message": "SELLO agent connected. Ready."},
        })
        while True:
            # Keep-alive: echo ping/pong
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(user_id, conn_id)
    except Exception as e:
        log.error("websocket.error", error=str(e))
        ws_manager.disconnect(user_id, conn_id)
