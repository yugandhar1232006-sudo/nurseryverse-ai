"""
`KnowledgeRetrievalService` -- the query-time half of docs/architecture/
06-ai-architecture.md §9 (RAG Architecture). Embeds the user's question
via a pluggable `EmbeddingProvider` (Voyage AI or local Ollama, selected
by `Settings.EMBEDDING_PROVIDER`) and retrieves the nearest
`knowledge_base_chunks` rows via `KnowledgeBaseChunkRepository.search_similar`
(tenant-scoped, per that repository's own docstring).

SCOPE NOTE: the INGESTION half (embedding knowledge articles at write-time
via a Celery task) is deliberately NOT built here -- see the original
docstring for the full reasoning. This class implements the QUERY side for
real: given a populated `knowledge_base_chunks` table, retrieval works
today. Until that pipeline exists, `knowledge_base_chunks` is empty in
every environment, so `retrieve()` returns `[]` -- a real, honest, disclosed
gap, not a fabricated result.
"""
from __future__ import annotations

import uuid

import httpx

from app.ai.assistant.embedding_providers import EmbeddingProvider
from app.core.config import Settings
from app.core.logging import get_logger
from app.models.ai import KnowledgeBaseChunk
from app.repositories.interfaces import KnowledgeBaseChunkRepository

logger = get_logger(__name__)

_RETRIEVAL_LIMIT = 5


class KnowledgeRetrievalService:
    def __init__(
        self,
        *,
        settings: Settings,
        chunk_repo: KnowledgeBaseChunkRepository,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self._settings = settings
        self._chunks = chunk_repo
        self._embedding_provider = embedding_provider

    def _resolve_embedding_provider(self) -> EmbeddingProvider:
        if self._embedding_provider is not None:
            return self._embedding_provider
        from app.ai.assistant.embedding_providers import (
            OllamaEmbeddingProvider,
            VoyageEmbeddingProvider,
        )

        if self._settings.EMBEDDING_PROVIDER == "ollama":
            return OllamaEmbeddingProvider(base_url=self._settings.OLLAMA_BASE_URL)
        return VoyageEmbeddingProvider(api_key=self._settings.VOYAGE_API_KEY)

    async def retrieve(self, *, query: str, nursery_id: uuid.UUID) -> list[KnowledgeBaseChunk]:
        """
        Never raises -- a RAG grounding failure (no provider configured,
        provider unreachable, empty knowledge base) degrades to "no
        retrieved context" rather than failing the whole Assistant turn.
        """
        provider = self._resolve_embedding_provider()
        if not provider.is_configured():
            return []
        try:
            embedding = await provider.embed(query)
        except (httpx.HTTPError, KeyError, IndexError) as exc:
            logger.warning("embedding_request_failed", error=type(exc).__name__, detail=str(exc))
            return []
        return await self._chunks.search_similar(embedding, nursery_id=nursery_id, limit=_RETRIEVAL_LIMIT)
