"""
SELLO — Database Models (SQLAlchemy 2.0 async)
Uses declarative base with typed columns.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional
from enum import Enum as PyEnum

from sqlalchemy import (
    String, Text, Integer, Float, Boolean, DateTime,
    ForeignKey, JSON, Enum, func, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for all models."""


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────

class UserRole(str, PyEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class LeadStatus(str, PyEnum):
    NEW = "new"
    RESEARCHING = "researching"
    SCORED = "scored"
    OUTREACH_DRAFT = "outreach_draft"
    OUTREACH_SENT = "outreach_sent"
    REPLIED = "replied"
    HUMAN_REVIEW = "human_review"
    QUALIFIED = "qualified"
    DISQUALIFIED = "disqualified"
    CUSTOMER = "customer"


class LeadTier(str, PyEnum):
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"


class Platform(str, PyEnum):
    REDDIT = "reddit"
    TWITTER = "twitter"
    LINKEDIN = "linkedin"
    GITHUB = "github"
    DISCORD = "discord"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    WEB = "web"
    MANUAL = "manual"


class CampaignStatus(str, PyEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class MessageDirection(str, PyEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    INTERNAL = "internal"  # agent notes


class AgentActionType(str, PyEnum):
    LEAD_DISCOVERED = "lead_discovered"
    LEAD_SCORED = "lead_scored"
    RESEARCH_COMPLETED = "research_completed"
    OUTREACH_DRAFTED = "outreach_drafted"
    OUTREACH_SENT = "outreach_sent"
    REPLY_RECEIVED = "reply_received"
    HUMAN_HANDOFF = "human_handoff"
    CRM_UPDATED = "crm_updated"


# ─────────────────────────────────────────────────────────────────────────────
# Mixins
# ─────────────────────────────────────────────────────────────────────────────

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False
    )


class UUIDMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


# ─────────────────────────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────────────────────────

class User(UUIDMixin, TimestampMixin, Base):
    """Platform user / account."""
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(200))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.MEMBER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500))

    # AI Preferences
    ai_model: Mapped[str] = mapped_column(String(100), default="qwen2.5:7b")
    ai_temperature: Mapped[float] = mapped_column(Float, default=0.7)
    ai_persona: Mapped[Optional[str]] = mapped_column(Text)  # Custom AI personality

    # Settings (JSON blob)
    notification_settings: Mapped[dict] = mapped_column(JSON, default=dict)
    platform_settings: Mapped[dict] = mapped_column(JSON, default=dict)

    # Relations
    campaigns: Mapped[list["Campaign"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    leads: Mapped[list["Lead"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="user")


class Campaign(UUIDMixin, TimestampMixin, Base):
    """A configured lead search campaign."""
    __tablename__ = "campaigns"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[CampaignStatus] = mapped_column(Enum(CampaignStatus), default=CampaignStatus.ACTIVE)

    # Search Config
    keywords: Mapped[list] = mapped_column(JSON, default=list)       # search keywords
    platforms: Mapped[list] = mapped_column(JSON, default=list)       # enabled platforms
    subreddits: Mapped[list] = mapped_column(JSON, default=list)      # reddit specific
    filters: Mapped[dict] = mapped_column(JSON, default=dict)         # min_score, exclude_spam, etc.

    # Schedule
    schedule_cron: Mapped[Optional[str]] = mapped_column(String(100)) # e.g. "0 9 * * 1-5"
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    run_count: Mapped[int] = mapped_column(Integer, default=0)

    # Stats
    leads_discovered: Mapped[int] = mapped_column(Integer, default=0)
    leads_qualified: Mapped[int] = mapped_column(Integer, default=0)

    # Relations
    user: Mapped["User"] = relationship(back_populates="campaigns")
    leads: Mapped[list["Lead"]] = relationship(back_populates="campaign")


class Lead(UUIDMixin, TimestampMixin, Base):
    """Unified lead record across all platforms."""
    __tablename__ = "leads"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    campaign_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("campaigns.id", ondelete="SET NULL"))

    # Identity
    platform: Mapped[Platform] = mapped_column(Enum(Platform), nullable=False)
    handle: Mapped[Optional[str]] = mapped_column(String(200))
    display_name: Mapped[Optional[str]] = mapped_column(String(200))
    profile_url: Mapped[Optional[str]] = mapped_column(String(500))
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500))
    email: Mapped[Optional[str]] = mapped_column(String(255))

    # Discovery Context
    source_post_url: Mapped[Optional[str]] = mapped_column(String(500))
    source_post_content: Mapped[Optional[str]] = mapped_column(Text)   # raw post that triggered discovery
    discovery_keywords: Mapped[list] = mapped_column(JSON, default=list)

    # Profile Data
    bio: Mapped[Optional[str]] = mapped_column(Text)
    followers: Mapped[int] = mapped_column(Integer, default=0)
    following: Mapped[int] = mapped_column(Integer, default=0)
    post_count: Mapped[int] = mapped_column(Integer, default=0)
    recent_posts: Mapped[Optional[str]] = mapped_column(Text)

    # Company / Business Research
    company_name: Mapped[Optional[str]] = mapped_column(String(300))
    company_website: Mapped[Optional[str]] = mapped_column(String(500))
    company_industry: Mapped[Optional[str]] = mapped_column(String(200))
    company_size: Mapped[Optional[str]] = mapped_column(String(100))
    tech_stack: Mapped[list] = mapped_column(JSON, default=list)
    business_category: Mapped[Optional[str]] = mapped_column(String(200))

    # AI Scoring
    lead_score: Mapped[Optional[float]] = mapped_column(Float)         # 0.0 – 10.0
    tier: Mapped[Optional[LeadTier]] = mapped_column(Enum(LeadTier))
    buying_intent_score: Mapped[Optional[float]] = mapped_column(Float)
    urgency_score: Mapped[Optional[float]] = mapped_column(Float)
    budget_estimate: Mapped[Optional[str]] = mapped_column(String(200))
    is_spam: Mapped[bool] = mapped_column(Boolean, default=False)
    quality_flags: Mapped[list] = mapped_column(JSON, default=list)    # ["no_website", "bot_suspected"]

    # Intent
    detected_intent: Mapped[Optional[str]] = mapped_column(Text)
    pain_points: Mapped[list] = mapped_column(JSON, default=list)
    competitor_mentions: Mapped[list] = mapped_column(JSON, default=list)
    buying_signals: Mapped[list] = mapped_column(JSON, default=list)

    # Pipeline
    status: Mapped[LeadStatus] = mapped_column(Enum(LeadStatus), default=LeadStatus.NEW)
    pipeline_stage: Mapped[Optional[str]] = mapped_column(String(100))
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    # Outreach
    outreach_draft: Mapped[Optional[str]] = mapped_column(Text)
    outreach_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_contacted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    follow_up_count: Mapped[int] = mapped_column(Integer, default=0)
    next_follow_up_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # CRM
    crm_notes: Mapped[Optional[str]] = mapped_column(Text)
    deal_value: Mapped[Optional[float]] = mapped_column(Float)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    custom_fields: Mapped[dict] = mapped_column(JSON, default=dict)

    # Raw research data (for RAG)
    research_summary: Mapped[Optional[str]] = mapped_column(Text)
    qdrant_point_id: Mapped[Optional[str]] = mapped_column(String(100))  # vector DB reference

    # Relations
    user: Mapped["User"] = relationship(back_populates="leads")
    campaign: Mapped[Optional["Campaign"]] = relationship(back_populates="leads")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="lead", cascade="all, delete-orphan")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="lead")

    __table_args__ = (
        Index("ix_leads_user_status", "user_id", "status"),
        Index("ix_leads_platform", "platform"),
        Index("ix_leads_score", "lead_score"),
    )


class Conversation(UUIDMixin, TimestampMixin, Base):
    """Message thread for a lead."""
    __tablename__ = "conversations"

    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"))
    subject: Mapped[Optional[str]] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    language: Mapped[str] = mapped_column(String(20), default="en")
    tone: Mapped[str] = mapped_column(String(50), default="professional")  # professional, casual, friendly
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    last_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relations
    lead: Mapped["Lead"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")


class Message(UUIDMixin, TimestampMixin, Base):
    """Individual message in a conversation."""
    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    direction: Mapped[MessageDirection] = mapped_column(Enum(MessageDirection))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sender: Mapped[str] = mapped_column(String(200))  # "AI", "Human", or lead handle
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    sent_via_platform: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata: Mapped[dict] = mapped_column(JSON, default=dict)

    # AI learning tags
    was_successful: Mapped[Optional[bool]] = mapped_column(Boolean)
    human_rating: Mapped[Optional[int]] = mapped_column(Integer)  # 1-5

    # Relations
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


class KnowledgeDocument(UUIDMixin, TimestampMixin, Base):
    """RAG knowledge base documents."""
    __tablename__ = "knowledge_documents"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    doc_type: Mapped[str] = mapped_column(String(50))  # "company_info", "pricing", "case_study"
    qdrant_point_ids: Mapped[list] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PromptTemplate(UUIDMixin, TimestampMixin, Base):
    """Editable prompt templates per agent."""
    __tablename__ = "prompt_templates"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)  # "lead_scorer", "conversation"
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    variables: Mapped[list] = mapped_column(JSON, default=list)  # ["handle", "bio", "intent"]
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    success_rate: Mapped[Optional[float]] = mapped_column(Float)


class AuditLog(UUIDMixin, Base):
    """Immutable audit log for all agent actions."""
    __tablename__ = "audit_logs"

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    lead_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("leads.id", ondelete="SET NULL"))
    action_type: Mapped[AgentActionType] = mapped_column(Enum(AgentActionType))
    agent_name: Mapped[str] = mapped_column(String(100))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Relations
    user: Mapped[Optional["User"]] = relationship(back_populates="audit_logs")
    lead: Mapped[Optional["Lead"]] = relationship(back_populates="audit_logs")

    __table_args__ = (
        Index("ix_audit_user_created", "user_id", "created_at"),
        Index("ix_audit_action", "action_type"),
    )
