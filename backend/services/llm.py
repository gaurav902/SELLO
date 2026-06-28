"""
SELLO — LLM & Embedding Service (Ollama)
"""

from __future__ import annotations

import httpx
import structlog
from typing import Any, Optional
from core.config import get_settings

log = structlog.get_logger(__name__)
cfg = get_settings()


class LLMService:
    """Interacts with local Ollama instance for completions and embeddings."""

    def __init__(self, base_url: Optional[str] = None) -> None:
        self.base_url = base_url or cfg.ollama_base_url
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=60.0)

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: float = 0.7,
        format: Optional[str] = None,
    ) -> str:
        """Call Ollama generation API endpoint."""
        selected_model = model or cfg.ollama_default_model
        payload = {
            "model": selected_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
            }
        }
        if system:
            payload["system"] = system
        if format:
            payload["format"] = format

        try:
            response = await self.client.post("/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "").strip()
        except Exception as e:
            log.error("llm.generate_failed", error=str(e), model=selected_model)
            raise RuntimeError(f"Ollama generate request failed: {e}")

    async def get_embeddings(self, text: str, model: Optional[str] = None) -> list[float]:
        """Generate embedding vector for text using Ollama embedding model."""
        selected_model = model or cfg.ollama_embedding_model
        payload = {
            "model": selected_model,
            "prompt": text,
        }
        try:
            response = await self.client.post("/api/embeddings", json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("embedding", [])
        except Exception as e:
            log.error("llm.embeddings_failed", error=str(e), model=selected_model)
            raise RuntimeError(f"Ollama embeddings request failed: {e}")

    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()


# Singleton instance
llm_service = LLMService()
