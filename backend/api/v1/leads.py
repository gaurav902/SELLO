"""
SELLO — Leads API Router (/api/v1/leads)
"""

from __future__ import annotations

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import CurrentUser
from database.session import get_session
from database.models import Lead, LeadStatus, LeadTier, Platform

router = APIRouter(prefix="/leads", tags=["Leads"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class LeadCreate(BaseModel):
    platform: Platform
    handle: Optional[str] = None
    display_name: Optional[str] = None
    profile_url: Optional[str] = None
    bio: Optional[str] = None
    source_post_content: Optional[str] = None


class LeadUpdate(BaseModel):
    status: Optional[LeadStatus] = None
    pipeline_stage: Optional[str] = None
    outreach_draft: Optional[str] = None
    crm_notes: Optional[str] = None
    deal_value: Optional[float] = None
    tags: Optional[list[str]] = None


class LeadResponse(BaseModel):
    id: str
    platform: str
    handle: Optional[str]
    display_name: Optional[str]
    profile_url: Optional[str]
    bio: Optional[str]
    followers: int
    lead_score: Optional[float]
    tier: Optional[str]
    buying_intent_score: Optional[float]
    status: str
    detected_intent: Optional[str]
    outreach_draft: Optional[str]
    crm_notes: Optional[str]
    deal_value: Optional[float]
    tags: list
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class PaginatedLeads(BaseModel):
    items: list[LeadResponse]
    total: int
    page: int
    per_page: int
    pages: int


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("", response_model=PaginatedLeads)
async def list_leads(
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    status: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    tier: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
) -> PaginatedLeads:
    """Paginated, filtered lead list for the current user."""
    filters = [Lead.user_id == current_user.id]

    if status:
        filters.append(Lead.status == status)
    if platform:
        filters.append(Lead.platform == platform)
    if tier:
        filters.append(Lead.tier == tier)
    if search:
        filters.append(
            Lead.handle.ilike(f"%{search}%") |
            Lead.display_name.ilike(f"%{search}%") |
            Lead.bio.ilike(f"%{search}%")
        )

    total_result = await session.execute(
        select(func.count()).select_from(Lead).where(and_(*filters))
    )
    total = total_result.scalar_one()

    offset = (page - 1) * per_page
    leads_result = await session.execute(
        select(Lead)
        .where(and_(*filters))
        .order_by(Lead.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    leads = leads_result.scalars().all()

    return PaginatedLeads(
        items=[LeadResponse.model_validate(l) for l in leads],
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page,
    )


@router.post("", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(
    body: LeadCreate,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LeadResponse:
    """Manually add a lead."""
    lead = Lead(
        user_id=current_user.id,
        **body.model_dump(exclude_none=True),
    )
    session.add(lead)
    await session.flush()
    await session.refresh(lead)
    return LeadResponse.model_validate(lead)


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LeadResponse:
    result = await session.execute(
        select(Lead).where(Lead.id == lead_id, Lead.user_id == current_user.id)
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return LeadResponse.model_validate(lead)


@router.patch("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: uuid.UUID,
    body: LeadUpdate,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LeadResponse:
    result = await session.execute(
        select(Lead).where(Lead.id == lead_id, Lead.user_id == current_user.id)
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(lead, field, value)

    await session.flush()
    await session.refresh(lead)
    return LeadResponse.model_validate(lead)


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(
    lead_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    result = await session.execute(
        select(Lead).where(Lead.id == lead_id, Lead.user_id == current_user.id)
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    await session.delete(lead)


@router.get("/stats/overview")
async def leads_stats(
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """Quick stats for the dashboard."""
    base = select(func.count()).select_from(Lead).where(Lead.user_id == current_user.id)

    async def count(extra_filter=None):
        stmt = base if extra_filter is None else base.where(extra_filter)
        result = await session.execute(stmt)
        return result.scalar_one()

    return {
        "total": await count(),
        "new": await count(Lead.status == LeadStatus.NEW),
        "scored": await count(Lead.status == LeadStatus.SCORED),
        "outreach_sent": await count(Lead.status == LeadStatus.OUTREACH_SENT),
        "replied": await count(Lead.status == LeadStatus.REPLIED),
        "qualified": await count(Lead.status == LeadStatus.QUALIFIED),
        "hot": await count(Lead.tier == LeadTier.HOT),
        "warm": await count(Lead.tier == LeadTier.WARM),
    }
