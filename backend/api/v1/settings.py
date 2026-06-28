"""
SELLO — Settings API (/api/v1/settings)
User preferences + AI configuration.
"""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import CurrentUser
from database.session import get_session

router = APIRouter(prefix="/settings", tags=["Settings"])


class AISettings(BaseModel):
    ai_model: Optional[str] = None
    ai_temperature: Optional[float] = None
    ai_persona: Optional[str] = None


class NotificationSettings(BaseModel):
    telegram_enabled: bool = False
    email_enabled: bool = False
    slack_enabled: bool = False
    discord_enabled: bool = False
    notify_on_new_lead: bool = True
    notify_on_human_review: bool = True
    notify_on_reply: bool = True


class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    username: Optional[str] = None
    avatar_url: Optional[str] = None


class SettingsResponse(BaseModel):
    ai_model: str
    ai_temperature: float
    ai_persona: Optional[str]
    notification_settings: dict
    platform_settings: dict
    full_name: Optional[str]
    username: str
    email: str


@router.get("", response_model=SettingsResponse)
async def get_settings(current_user: CurrentUser) -> SettingsResponse:
    return SettingsResponse(
        ai_model=current_user.ai_model,
        ai_temperature=current_user.ai_temperature,
        ai_persona=current_user.ai_persona,
        notification_settings=current_user.notification_settings or {},
        platform_settings=current_user.platform_settings or {},
        full_name=current_user.full_name,
        username=current_user.username,
        email=current_user.email,
    )


@router.patch("/ai", response_model=SettingsResponse)
async def update_ai_settings(
    body: AISettings,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SettingsResponse:
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(current_user, field, value)
    await session.flush()
    return await get_settings(current_user)


@router.patch("/notifications", response_model=SettingsResponse)
async def update_notifications(
    body: NotificationSettings,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SettingsResponse:
    current_user.notification_settings = body.model_dump()
    await session.flush()
    return await get_settings(current_user)


@router.patch("/profile", response_model=SettingsResponse)
async def update_profile(
    body: UserProfileUpdate,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SettingsResponse:
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(current_user, field, value)
    await session.flush()
    return await get_settings(current_user)


@router.get("/ollama/models")
async def list_ollama_models(current_user: CurrentUser) -> dict:
    """Fetch available models from local Ollama instance."""
    import httpx
    from core.config import get_settings
    cfg = get_settings()
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{cfg.ollama_base_url}/api/tags", timeout=5.0)
            data = response.json()
            models = [m["name"] for m in data.get("models", [])]
            return {"models": models, "default": cfg.ollama_default_model}
    except Exception:
        return {"models": [], "default": cfg.ollama_default_model, "error": "Ollama not reachable"}
