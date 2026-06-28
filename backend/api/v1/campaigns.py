"""
SELLO — Campaigns API Router (/api/v1/campaigns)
"""

from __future__ import annotations

import uuid
from typing import Annotated, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import CurrentUser
from database.session import get_session
from database.models import Campaign, CampaignStatus

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])


class CampaignCreate(BaseModel):
    name: str
    description: Optional[str] = None
    keywords: list[str] = []
    platforms: list[str] = []
    subreddits: list[str] = []
    filters: dict = {}
    schedule_cron: Optional[str] = None


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[list[str]] = None
    platforms: Optional[list[str]] = None
    subreddits: Optional[list[str]] = None
    filters: Optional[dict] = None
    schedule_cron: Optional[str] = None
    status: Optional[CampaignStatus] = None


class CampaignResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    status: str
    keywords: list
    platforms: list
    subreddits: list
    filters: dict
    schedule_cron: Optional[str]
    last_run_at: Optional[str]
    run_count: int
    leads_discovered: int
    leads_qualified: int
    created_at: str

    model_config = {"from_attributes": True}


@router.get("", response_model=list[CampaignResponse])
async def list_campaigns(
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[CampaignResponse]:
    result = await session.execute(
        select(Campaign)
        .where(Campaign.user_id == current_user.id)
        .order_by(Campaign.created_at.desc())
    )
    return [CampaignResponse.model_validate(c) for c in result.scalars().all()]


@router.post("", response_model=CampaignResponse, status_code=201)
async def create_campaign(
    body: CampaignCreate,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CampaignResponse:
    campaign = Campaign(user_id=current_user.id, **body.model_dump())
    session.add(campaign)
    await session.flush()
    await session.refresh(campaign)
    return CampaignResponse.model_validate(campaign)


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CampaignResponse:
    result = await session.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == current_user.id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return CampaignResponse.model_validate(campaign)


@router.patch("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: uuid.UUID,
    body: CampaignUpdate,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CampaignResponse:
    result = await session.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == current_user.id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(campaign, field, value)

    await session.flush()
    await session.refresh(campaign)
    return CampaignResponse.model_validate(campaign)


from fastapi import BackgroundTasks
from services.campaign import execute_campaign

@router.post("/{campaign_id}/run", status_code=202)
async def run_campaign(
    campaign_id: uuid.UUID,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """Trigger the agent pipeline for a campaign (async, returns immediately)."""
    result = await session.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == current_user.id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    background_tasks.add_task(execute_campaign, str(campaign_id), str(current_user.id))
    return {
        "message": "Campaign pipeline started",
        "campaign_id": str(campaign_id),
        "status": "queued",
    }


@router.delete("/{campaign_id}", status_code=204)
async def delete_campaign(
    campaign_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    result = await session.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == current_user.id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    await session.delete(campaign)
