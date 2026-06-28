"""
SELLO — Qdrant Vector Database Service
"""

from __future__ import annotations

import structlog
from typing import Any, Optional, list, dict
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from core.config import get_settings
from services.llm import llm_service

log = structlog.get_logger(__name__)
cfg = get_settings()


class VectorDBService:
    """Interacts with Qdrant for semantic search and RAG storage."""

    def __init__(self) -> None:
        self.client = QdrantClient(url=cfg.qdrant_url)
        self.lead_collection = cfg.qdrant_collection_leads
        self.memory_collection = cfg.qdrant_collection_memory

    def init_collections(self) -> None:
        """Create collections if they do not exist (vector size = 768 for nomic-embed-text)."""
        for collection in [self.lead_collection, self.memory_collection]:
            try:
                if not self.client.collection_exists(collection_name=collection):
                    self.client.create_collection(
                        collection_name=collection,
                        vectors_config=VectorParams(size=768, distance=Distance.COSINE),
                    )
                    log.info("qdrant.collection_created", collection=collection)
            except Exception as e:
                log.error("qdrant.init_failed", collection=collection, error=str(e))

    async def upsert_lead(self, lead_id: str, text: str, payload: dict[str, Any]) -> None:
        """Embed and index a lead in Qdrant."""
        try:
            vector = await llm_service.get_embeddings(text)
            self.client.upsert(
                collection_name=self.lead_collection,
                points=[
                    PointStruct(
                        id=lead_id,
                        vector=vector,
                        payload={**payload, "text": text}
                    )
                ]
            )
            log.info("qdrant.upsert_lead_success", lead_id=lead_id)
        except Exception as e:
            log.error("qdrant.upsert_lead_failed", lead_id=lead_id, error=str(e))

    async def upsert_memory(self, memory_id: str, text: str, payload: dict[str, Any]) -> None:
        """Embed and index a memory snippet."""
        try:
            vector = await llm_service.get_embeddings(text)
            self.client.upsert(
                collection_name=self.memory_collection,
                points=[
                    PointStruct(
                        id=memory_id,
                        vector=vector,
                        payload={**payload, "text": text}
                    )
                ]
            )
            log.info("qdrant.upsert_memory_success", memory_id=memory_id)
        except Exception as e:
            log.error("qdrant.upsert_memory_failed", memory_id=memory_id, error=str(e))

    async def search_leads(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search similar leads by query text."""
        try:
            vector = await llm_service.get_embeddings(query)
            results = self.client.search(
                collection_name=self.lead_collection,
                query_vector=vector,
                limit=limit
            )
            return [
                {
                    "id": str(r.id),
                    "score": r.score,
                    "payload": r.payload
                }
                for r in results
            ]
        except Exception as e:
            log.error("qdrant.search_leads_failed", query=query, error=str(e))
            return []

    async def search_memory(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search relevant memory context by query text."""
        try:
            vector = await llm_service.get_embeddings(query)
            results = self.client.search(
                collection_name=self.memory_collection,
                query_vector=vector,
                limit=limit
            )
            return [
                {
                    "id": str(r.id),
                    "score": r.score,
                    "payload": r.payload
                }
                for r in results
            ]
        except Exception as e:
            log.error("qdrant.search_memory_failed", query=query, error=str(e))
            return []


# Singleton instance
vector_service = VectorDBService()
