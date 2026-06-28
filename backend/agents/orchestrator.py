"""
SELLO — LangGraph Agent Pipeline Orchestrator
Connects intent detection, company research, scoring, copywriting, and notifications.
"""

from __future__ import annotations

import json
import uuid
import structlog
from typing import Any, Optional
from langgraph.graph import StateGraph, END
from sqlalchemy import select

from database.session import AsyncSessionFactory
from database.models import Lead, LeadStatus, LeadTier, AuditLog, AgentActionType
from database.models import User, Message, MessageDirection, Conversation
from agents.state import AgentState
from services.llm import llm_service
from services.vector_db import vector_service
from websocket.manager import emit

log = structlog.get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Node 1: Intent Detection
# ─────────────────────────────────────────────────────────────────────────────
async def detect_intent_node(state: AgentState) -> dict[str, Any]:
    """Analyze post content to determine buying intent, pain points, and competitors."""
    lead_id = state["lead_id"]
    log.info("agent.intent_detection.start", lead_id=lead_id)

    async with AsyncSessionFactory() as session:
        result = await session.execute(select(Lead).where(Lead.id == uuid.UUID(lead_id)))
        lead = result.scalar_one_or_none()
        if not lead:
            log.error("agent.intent_detection.error", lead_id=lead_id, reason="Lead not found")
            return {}

        content = lead.source_post_content or ""

    # Prompt LLM for structured intent analysis
    system_prompt = (
        "You are an expert lead analyst. Analyze the user's social media post/query "
        "and return a JSON response with the following keys:\n"
        "- intent: A concise summary of what they want/need.\n"
        "- pain_points: A list of key problems they are facing.\n"
        "- buying_signals: A list of words or phrases indicating willingness to pay/hire.\n"
        "- competitor_mentions: Any software or agencies they mention.\n"
        "Your output must be valid JSON only. Do not wrap in markdown code blocks."
    )

    try:
        raw_response = await llm_service.generate(
            prompt=f"Post content: {content}",
            system=system_prompt,
            format="json"
        )
        parsed = json.loads(raw_response)
    except Exception as e:
        log.warning("agent.intent_detection.llm_failed", error=str(e))
        # Fallback values
        parsed = {
            "intent": "Inquired about services",
            "pain_points": ["Unspecified pain points"],
            "buying_signals": [],
            "competitor_mentions": []
        }

    # Save to database
    async with AsyncSessionFactory() as session:
        result = await session.execute(select(Lead).where(Lead.id == uuid.UUID(lead_id)))
        lead = result.scalar_one_or_none()
        if lead:
            lead.detected_intent = parsed.get("intent")
            lead.pain_points = parsed.get("pain_points", [])
            lead.buying_signals = parsed.get("buying_signals", [])
            lead.competitor_mentions = parsed.get("competitor_mentions", [])
            lead.status = LeadStatus.RESEARCHING
            await session.commit()

    return {
        "detected_intent": parsed.get("intent"),
        "pain_points": parsed.get("pain_points", []),
        "buying_signals": parsed.get("buying_signals", []),
        "competitor_mentions": parsed.get("competitor_mentions", [])
    }


# ─────────────────────────────────────────────────────────────────────────────
# Node 2: Profile & Company Research
# ─────────────────────────────────────────────────────────────────────────────
async def research_node(state: AgentState) -> dict[str, Any]:
    """Research the lead's bio, company, website, and technology stack."""
    lead_id = state["lead_id"]
    log.info("agent.research.start", lead_id=lead_id)

    async with AsyncSessionFactory() as session:
        result = await session.execute(select(Lead).where(Lead.id == uuid.UUID(lead_id)))
        lead = result.scalar_one_or_none()
        if not lead:
            return {}

        bio = lead.bio or ""
        post_content = lead.source_post_content or ""

    # Infer business details using LLM
    system_prompt = (
        "You are an OSINT research analyst. Based on this user bio and post, "
        "infer as much business detail as possible. Return a JSON response with:\n"
        "- company_name: Inferred name (or null).\n"
        "- company_website: Inferred or guessed domain (or null).\n"
        "- company_industry: e.g. SaaS, E-commerce, Finance, Healthcare, agency.\n"
        "- tech_stack: List of technologies mentioned or likely used (e.g. ['React', 'PostgreSQL']).\n"
        "- business_category: Category description.\n"
        "Your output must be valid JSON only."
    )

    try:
        raw_response = await llm_service.generate(
            prompt=f"Bio: {bio}\nPost: {post_content}",
            system=system_prompt,
            format="json"
        )
        parsed = json.loads(raw_response)
    except Exception as e:
        log.warning("agent.research.llm_failed", error=str(e))
        parsed = {
            "company_name": None,
            "company_website": None,
            "company_industry": "Technology",
            "tech_stack": [],
            "business_category": "Unknown"
        }

    # Save to database
    async with AsyncSessionFactory() as session:
        result = await session.execute(select(Lead).where(Lead.id == uuid.UUID(lead_id)))
        lead = result.scalar_one_or_none()
        if lead:
            lead.company_name = parsed.get("company_name")
            lead.company_website = parsed.get("company_website")
            lead.company_industry = parsed.get("company_industry")
            lead.tech_stack = parsed.get("tech_stack", [])
            lead.business_category = parsed.get("business_category")
            await session.commit()

    return {
        "company_name": parsed.get("company_name"),
        "company_website": parsed.get("company_website"),
        "company_industry": parsed.get("company_industry"),
        "tech_stack": parsed.get("tech_stack", []),
        "business_category": parsed.get("business_category")
    }


# ─────────────────────────────────────────────────────────────────────────────
# Node 3: Lead Scoring
# ─────────────────────────────────────────────────────────────────────────────
async def score_lead_node(state: AgentState) -> dict[str, Any]:
    """Calculate lead quality, buying intent, urgency, budget, and overall score."""
    lead_id = state["lead_id"]
    log.info("agent.scoring.start", lead_id=lead_id)

    async with AsyncSessionFactory() as session:
        result = await session.execute(select(Lead).where(Lead.id == uuid.UUID(lead_id)))
        lead = result.scalar_one_or_none()
        if not lead:
            return {}

        post = lead.source_post_content or ""
        intent = lead.detected_intent or ""

    # Perform score calculations via LLM
    system_prompt = (
        "You are a sales qualification specialist. Grade this prospective lead from 0.0 to 10.0.\n"
        "Return a JSON response with:\n"
        "- lead_score: Overall grade float (0.0 to 10.0).\n"
        "- buying_intent_score: Float (0.0 to 10.0).\n"
        "- urgency_score: Float (0.0 to 10.0).\n"
        "- budget_estimate: Inferred budget (e.g. '$10k+', '$2k-$5k', or 'Unknown').\n"
        "- is_spam: Boolean indicating if this is spam/advertisement.\n"
        "- quality_flags: List of indicators like ['high_intent', 'unspecified_budget'].\n"
        "Your output must be valid JSON only."
    )

    try:
        raw_response = await llm_service.generate(
            prompt=f"Post: {post}\nIntent: {intent}",
            system=system_prompt,
            format="json"
        )
        parsed = json.loads(raw_response)
    except Exception as e:
        log.warning("agent.scoring.llm_failed", error=str(e))
        parsed = {
            "lead_score": 5.0,
            "buying_intent_score": 5.0,
            "urgency_score": 5.0,
            "budget_estimate": "Unknown",
            "is_spam": False,
            "quality_flags": []
        }

    # Map tier
    score = parsed.get("lead_score", 5.0)
    if score >= 8.0:
        tier = LeadTier.HOT
    elif score >= 5.0:
        tier = LeadTier.WARM
    else:
        tier = LeadTier.COLD

    async with AsyncSessionFactory() as session:
        result = await session.execute(select(Lead).where(Lead.id == uuid.UUID(lead_id)))
        lead = result.scalar_one_or_none()
        if lead:
            lead.lead_score = score
            lead.buying_intent_score = parsed.get("buying_intent_score", 5.0)
            lead.urgency_score = parsed.get("urgency_score", 5.0)
            lead.budget_estimate = parsed.get("budget_estimate")
            lead.is_spam = parsed.get("is_spam", False)
            lead.quality_flags = parsed.get("quality_flags", [])
            lead.tier = tier
            lead.status = LeadStatus.SCORED
            await session.commit()

    return {
        "lead_score": score,
        "tier": tier.value,
        "is_spam": parsed.get("is_spam", False),
        "urgency_score": parsed.get("urgency_score", 5.0),
        "budget_estimate": parsed.get("budget_estimate")
    }


# ─────────────────────────────────────────────────────────────────────────────
# Node 4: Conversation Outreach Drafting
# ─────────────────────────────────────────────────────────────────────────────
async def draft_outreach_node(state: AgentState) -> dict[str, Any]:
    """Draft a personalized outreach message matching the user's settings and persona."""
    lead_id = state["lead_id"]
    user_id = state["user_id"]
    log.info("agent.conversation.start", lead_id=lead_id)

    async with AsyncSessionFactory() as session:
        result = await session.execute(select(Lead).where(Lead.id == uuid.UUID(lead_id)))
        lead = result.scalar_one_or_none()

        user_result = await session.execute(select(User).where(User.id == uuid.UUID(user_id)))
        user = user_result.scalar_one_or_none()

        if not lead or not user:
            return {}

        post = lead.source_post_content or ""
        intent = lead.detected_intent or ""
        persona = user.ai_persona or "A helpful professional business developer"
        temp = user.ai_temperature

    # Generate custom draft response matching user persona
    system_prompt = (
        f"You are SELLO - an AI business development assistant working on behalf of {user.full_name or user.username}.\n"
        f"Your AI Persona guidelines: {persona}.\n"
        "Draft a highly personalized, non-spammy, helpful first message/reply. "
        "Address their pain points, mention how you can help, and invite them for a quick chat/call. "
        "Keep it concise, friendly, and tailored to the post content."
    )

    try:
        draft = await llm_service.generate(
            prompt=f"Post to reply to: {post}\nDetected Intent: {intent}",
            system=system_prompt,
            temperature=temp
        )
    except Exception as e:
        log.warning("agent.conversation.llm_failed", error=str(e))
        draft = "Hi there, I saw your post and would love to help you out with this! Let's connect."

    # Save to database
    async with AsyncSessionFactory() as session:
        result = await session.execute(select(Lead).where(Lead.id == uuid.UUID(lead_id)))
        lead = result.scalar_one_or_none()
        if lead:
            lead.outreach_draft = draft
            lead.status = LeadStatus.OUTREACH_DRAFT
            await session.commit()

    return {"outreach_draft": draft}


# ─────────────────────────────────────────────────────────────────────────────
# Node 5: Notifications & Audit Logging
# ─────────────────────────────────────────────────────────────────────────────
async def notification_node(state: AgentState) -> dict[str, Any]:
    """Trigger real-time events, notify channels (Telegram, etc.), and log actions."""
    lead_id = state["lead_id"]
    user_id = state["user_id"]
    tier = state.get("tier", "cold")
    score = state.get("lead_score", 0.0)

    log.info("agent.notification.start", lead_id=lead_id, tier=tier)

    # Trigger WebSocket Broadcast
    await emit(user_id, "lead_processed", {
        "lead_id": lead_id,
        "tier": tier,
        "score": score,
        "message": f"Lead {state.get('handle', 'anonymous')} processed. Tier: {tier} ({score}/10)"
    })

    # Log action to audit logs
    async with AsyncSessionFactory() as session:
        log_entry = AuditLog(
            user_id=uuid.UUID(user_id),
            lead_id=uuid.UUID(lead_id),
            action_type=AgentActionType.OUTREACH_DRAFTED,
            agent_name="LangGraph Orchestrator",
            details={
                "tier": tier,
                "score": score,
                "intent": state.get("detected_intent"),
                "budget": state.get("budget_estimate"),
            },
            success=True
        )
        session.add(log_entry)

        # RAG Embedding indexing inside Qdrant vector DB
        lead_result = await session.execute(select(Lead).where(Lead.id == uuid.UUID(lead_id)))
        lead = lead_result.scalar_one_or_none()
        if lead:
            text = f"Lead handle: {lead.handle}. Bio: {lead.bio or ''}. Post: {lead.source_post_content}. Intent: {lead.detected_intent}. Inferred Stack: {', '.join(lead.tech_stack)}"
            # Index lead in background vector DB
            await vector_service.upsert_lead(
                lead_id=lead_id,
                text=text,
                payload={
                    "user_id": user_id,
                    "platform": lead.platform.value,
                    "handle": lead.handle,
                    "score": score,
                }
            )

        await session.commit()

    return {}


# ─────────────────────────────────────────────────────────────────────────────
# Compile LangGraph
# ─────────────────────────────────────────────────────────────────────────────
builder = StateGraph(AgentState)

# Add all node functions
builder.add_node("intent", detect_intent_node)
builder.add_node("research", research_node)
builder.add_node("scoring", score_lead_node)
builder.add_node("drafting", draft_outreach_node)
builder.add_node("notification", notification_node)

# Set entry point
builder.set_entry_point("intent")

# Define edges (Linear sequence of intelligence routing)
builder.add_edge("intent", "research")
builder.add_edge("research", "scoring")
builder.add_edge("scoring", "drafting")
builder.add_edge("drafting", "notification")
builder.add_edge("notification", END)

orchestrator_graph = builder.compile()


# Helper to run the pipeline
async def run_agent_pipeline(lead_id: str, user_id: str, campaign_id: Optional[str] = None) -> dict[str, Any]:
    """Execute the full agent workflow for a given lead."""
    async with AsyncSessionFactory() as session:
        result = await session.execute(select(Lead).where(Lead.id == uuid.UUID(lead_id)))
        lead = result.scalar_one_or_none()
        if not lead:
            raise ValueError(f"Lead with id {lead_id} not found.")

        initial_state: AgentState = {
            "lead_id": lead_id,
            "user_id": user_id,
            "campaign_id": campaign_id,
            "platform": lead.platform,
            "handle": lead.handle,
            "source_post_content": lead.source_post_content or "",
            "source_post_url": lead.source_post_url,
            "detected_intent": None,
            "pain_points": [],
            "buying_signals": [],
            "competitor_mentions": [],
            "company_name": None,
            "company_website": None,
            "company_industry": None,
            "tech_stack": [],
            "business_category": None,
            "lead_score": 0.0,
            "tier": "cold",
            "is_spam": False,
            "urgency_score": 0.0,
            "budget_estimate": None,
            "outreach_draft": None,
        }

    log.info("orchestrator.run.start", lead_id=lead_id)
    try:
        final_state = await orchestrator_graph.ainvoke(initial_state)
        log.info("orchestrator.run.complete", lead_id=lead_id)
        return final_state
    except Exception as e:
        log.error("orchestrator.run.failed", lead_id=lead_id, error=str(e))
        raise
