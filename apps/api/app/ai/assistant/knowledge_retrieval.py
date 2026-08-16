"""
`KnowledgeRetrievalService` -- the query-time half of docs/architecture/
06-ai-architecture.md §9 (RAG Architecture): "D -- Yes --> E[pgvector
similarity search - species knowledge, past disease reports]". Embeds the
user's question via the real Voyage AI embeddings API (`Settings.
VOYAGE_API_KEY`, matching `app/models/ai.py`'s `EMBEDDING_DIM=1024` =
voyage-3's dimension) and retrieves the nearest `knowledge_base_chunks`
rows via `KnowledgeBaseChunkRepository.search_similar` (tenant-scoped,
per that repository's own docstring).

SCOPE NOTE (disclosed in full in the Module 10 completion report): §8 of
the same architecture doc says embeddings are generated "at write-time
(new species record, new confirmed disease report) via a Celery task" --
that INGESTION half is deliberately NOT built here. No Celery worker
infrastructure exists anywhere in this codebase yet (no `app/workers/`
package, no Celery app instantiated in any of Modules 1-9) -- building a
Species/Disease-Report embedding pipeline would mean inventing a new
piece of cross-cutting infrastructure no prior module has established a
pattern for, which the user's own governing instruction for this module
("do not invent functionality outside the existing architecture") counsels
against. This class implements the QUERY side for real, not a stub: given
a populated `knowledge_base_chunks` table (from a future ingestion
pipeline), retrieval works today, unit-tested against the Fake repository.
Until that pipeline exists, `knowledge_base_chunks` is simply empty in
every environment, so `retrieve()` returns `[]` -- a real, honest, disclosed
gap (the same shape as `ModelRegistry`'s missing trained artifacts), not a
fabricated result. This does not break the Assistant: docs/architecture/
06-ai-architecture.md §9 itself ranks "structured tool-calls ... preferred
... retrieval/RAG is reserved specifically for the fuzzier, knowledge-style
questions" -- the Assistant's primary FR-9.1/9.2 answer path (tool-calling
into real service data) does not depend on RAG having any content.
"""
from __future__ import annotations

import uuid

import httpx

from app.core.config import Settings
from app.core.logging import get_logger
from app.models.ai import KnowledgeBaseChunk
from app.repositories.interfaces import KnowledgeBaseChunkRepository

logger = get_logger(__name__)

_VOYAGE_EMBEDDINGS_URL = "https://api.voyageai.com/v1/embeddings"
# voyage-3's output dimension (1024) matches `EMBEDDING_DIM` in app/models/ai.py -- the two must stay in
# lockstep (that model's own docstring: "If Phase 8 selects a different embedding model, this constant --
# and the `Vector(...)` column below -- must change together with a new migration").
_VOYAGE_MODEL = "voyage-3"
_RETRIEVAL_LIMIT = 5
_REQUEST_TIMEOUT_SECONDS = 10.0


class KnowledgeRetrievalService:
    def __init__(self, *, settings: Settings, chunk_repo: KnowledgeBaseChunkRepository) -> None:
        self._settings = settings
        self._chunks = chunk_repo

    async def retrieve(self, *, query: str, nursery_id: uuid.UUID) -> list[KnowledgeBaseChunk]:
        """
        Never raises -- a RAG grounding failure (no API key configured,
        Voyage unreachable, empty knowledge base) degrades to "no
        retrieved context" rather than failing the whole Assistant turn,
        per this module's own docstring on why RAG is an enhancement here,
        not a hard dependency (unlike Disease Detection's `ModelRegistry.
        get()`, which DOES raise, because that module has no other way to
        answer at all).
        """
        if not self._settings.VOYAGE_API_KEY:
            return []
        try:
            embedding = await self._embed(query)
        except (httpx.HTTPError, KeyError, IndexError) as exc:
            logger.warning("voyage_embedding_request_failed", error=type(exc).__name__, detail=str(exc))
            return []
        return await self._chunks.search_similar(embedding, nursery_id=nursery_id, limit=_RETRIEVAL_LIMIT)

    async def _embed(self, text: str) -> list[float]:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.post(
                _VOYAGE_EMBEDDINGS_URL,
                headers={"Authorization": f"Bearer {self._settings.VOYAGE_API_KEY}"},
                json={"input": [text], "model": _VOYAGE_MODEL, "input_type": "query"},
            )
            response.raise_for_status()
            data = response.json()
            embedding = data["data"][0]["embedding"]
            return [float(x) for x in embedding]
