"""
SELLO — Agent Pipeline State Definition
"""

from __future__ import annotations

from typing import TypedDict, Optional
from database.models import Platform


class AgentState(TypedDict):
    """Channels / State dictionary passed between LangGraph agent nodes."""
    lead_id: str
    user_id: str
    campaign_id: Optional[str]

    # Discovery Details
    platform: Platform
    handle: Optional[str]
    source_post_content: str
    source_post_url: Optional[str]

    # Intent
    detected_intent: Optional[str]
    pain_points: list[str]
    buying_signals: list[str]
    competitor_mentions: list[str]

    # Research
    company_name: Optional[str]
    company_website: Optional[str]
    company_industry: Optional[str]
    tech_stack: list[str]
    business_category: Optional[str]

    # Scoring
    lead_score: float
    tier: str
    is_spam: bool
    urgency_score: float
    budget_estimate: Optional[str]

    # Outreach
    outreach_draft: Optional[str]
