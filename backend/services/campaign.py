"""
SELLO — Campaign Runner Service
Fetches leads from connectors and triggers the agent pipeline.
"""

from __future__ import annotations

import uuid
import structlog
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select

from database.session import AsyncSessionFactory
from database.models import Campaign, Lead, LeadStatus
from connectors import get_connector
from database.models import Platform
from agents.orchestrator import run_agent_pipeline

log = structlog.get_logger(__name__)


async def execute_campaign(campaign_id: str, user_id: str) -> None:
    """Search for matching leads across platforms and process them through the AI pipeline."""
    log.info("campaign.execution.start", campaign_id=campaign_id)

    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(Campaign).where(Campaign.id == uuid.UUID(campaign_id))
        )
        campaign = result.scalar_one_or_none()
        if not campaign:
            log.error("campaign.execution.failed", campaign_id=campaign_id, reason="Campaign not found")
            return

        keywords = campaign.keywords or []
        platforms = campaign.platforms or []
        subreddits = campaign.subreddits or []
        campaign.last_run_at = datetime.now(timezone.utc)
        campaign.run_count += 1
        await session.commit()

    discovered_count = 0

    for platform_str in platforms:
        try:
            platform = Platform(platform_str.lower())
            connector = get_connector(platform)
        except Exception as e:
            log.warning("campaign.connector_error", platform=platform_str, error=str(e))
            continue

        for keyword in keywords:
            log.info("campaign.search", platform=platform_str, keyword=keyword)
            posts = await connector.search(keyword, limit=5)

            for post in posts:
                async with AsyncSessionFactory() as session:
                    # Deduplicate leads
                    existing = await session.execute(
                        select(Lead).where(
                            Lead.user_id == uuid.UUID(user_id),
                            Lead.source_post_url == post["source_post_url"]
                        )
                    )
                    if existing.scalar_one_or_none():
                        continue

                    # Create new Lead
                    lead = Lead(
                        user_id=uuid.UUID(user_id),
                        campaign_id=uuid.UUID(campaign_id),
                        platform=platform,
                        handle=post["handle"],
                        display_name=post["display_name"],
                        profile_url=post["profile_url"],
                        avatar_url=post["avatar_url"],
                        source_post_url=post["source_post_url"],
                        source_post_content=post["source_post_content"],
                        discovery_keywords=[keyword],
                        status=LeadStatus.NEW
                    )
                    session.add(lead)
                    await session.flush()
                    await session.refresh(lead)

                    lead_id_str = str(lead.id)
                    discovered_count += 1

                # Process lead through AI orchestrator
                try:
                    await run_agent_pipeline(lead_id_str, user_id, campaign_id)
                except Exception as e:
                    log.error("campaign.agent_pipeline_failed", lead_id=lead_id_str, error=str(e))

    # Update campaign stats
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(Campaign).where(Campaign.id == uuid.UUID(campaign_id))
        )
        campaign = result.scalar_one_or_none()
        if campaign:
            campaign.leads_discovered += discovered_count
            await session.commit()

    log.info("campaign.execution.complete", campaign_id=campaign_id, discovered=discovered_count)
