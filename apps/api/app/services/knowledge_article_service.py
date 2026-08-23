"""
Knowledge article management service for the RAG ingestion pipeline.

Handles CRUD for curated platform-wide horticultural knowledge articles
stored directly in `knowledge_base_chunks` with `source_type='knowledge_article'`
and `nursery_id=NULL`. Articles are chunked, embedded via the configured
EmbeddingProvider (Ollama or Voyage AI), and stored in pgvector for
similarity search by `KnowledgeRetrievalService`.

Idempotency: re-ingesting the same `source_ref` deletes all previous
chunks for that ref before creating new ones, so articles can be
safely updated without orphaned embeddings.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.ai.assistant.embedding_providers import EmbeddingProvider
from app.core.config import Settings
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.ai import EMBEDDING_DIM, KnowledgeBaseChunk
from app.repositories.interfaces import KnowledgeBaseChunkRepository

logger = get_logger(__name__)

# Maximum characters per chunk. Chunks are split on paragraph boundaries
# first; if a single paragraph exceeds this, it is split on sentence
# boundaries within the paragraph.
_MAX_CHUNK_CHARS = 1000
# Embedding model version label stored alongside each chunk, for future
# re-embedding campaigns (e.g. switching from mxbai-embed-large to a
# different model).
_EMBEDDING_MODEL_VERSION = "mxbai-embed-large-v1"


def chunk_text(text: str, *, max_chars: int = _MAX_CHUNK_CHARS) -> list[str]:
    """
    Split `text` into embedding-sized chunks, preferring paragraph
    boundaries (double newlines) and falling back to sentence boundaries
    within a paragraph. Each chunk is stripped of leading/trailing
    whitespace and empty strings are discarded.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    for para in paragraphs:
        if len(para) <= max_chars:
            chunks.append(para)
            continue
        # Split on sentence boundaries within the paragraph.
        sentences: list[str] = []
        current: list[str] = []
        for word in para.split(". "):
            if current:
                candidate = ". ".join(current) + ". " + word
            else:
                candidate = word
            if len(candidate) > max_chars and current:
                sentences.append(". ".join(current) + ".")
                current = [word]
            else:
                current.append(word)
        if current:
            remainder = ". ".join(current)
            if remainder and not remainder.endswith("."):
                remainder += "."
            sentences.append(remainder)
        for sent in sentences:
            if len(sent) <= max_chars:
                chunks.append(sent)
            else:
                # Last resort: hard split.
                for i in range(0, len(sent), max_chars):
                    chunk = sent[i : i + max_chars].strip()
                    if chunk:
                        chunks.append(chunk)
    return chunks


class KnowledgeArticleService:
    """CRUD + ingestion for platform-wide knowledge articles."""

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

    async def create_article(
        self,
        *,
        title: str,
        content: str,
        source_ref: str,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Create (or re-create) a knowledge article: chunk the content,
        embed each chunk, and persist to `knowledge_base_chunks`.

        Idempotent on `source_ref`: existing chunks with the same ref
        are deleted first, so re-ingestion replaces rather than
        duplicates.
        """
        provider = self._resolve_embedding_provider()
        if not provider.is_configured():
            raise ValidationError("Embedding provider is not configured")

        # Delete existing chunks for this source_ref (idempotency).
        await self._chunks.delete_by_source_ref(source_ref)

        # Chunk the content.
        chunks = chunk_text(content)
        if not chunks:
            raise ValidationError("Article content produces no chunks")

        # Embed and store each chunk.
        stored: list[KnowledgeBaseChunk] = []
        for idx, chunk_content in enumerate(chunks):
            chunk_title = title if idx == 0 else f"{title} (part {idx + 1})"
            try:
                embedding = await provider.embed(chunk_content)
            except (httpx.HTTPError, KeyError, IndexError) as exc:
                logger.warning(
                    "chunk_embedding_failed",
                    source_ref=source_ref,
                    chunk_index=idx,
                    error=type(exc).__name__,
                    detail=str(exc),
                )
                raise ValidationError(f"Failed to embed chunk {idx + 1}: {exc}") from exc

            if len(embedding) != EMBEDDING_DIM:
                raise ValidationError(
                    f"Embedding dimension mismatch: expected {EMBEDDING_DIM}, got {len(embedding)}"
                )

            chunk = KnowledgeBaseChunk(
                nursery_id=None,
                source_type="knowledge_article",
                source_ref=source_ref,
                title=chunk_title,
                content=chunk_content,
                embedding=embedding,
                embedding_model_version=_EMBEDDING_MODEL_VERSION,
            )
            stored.append(await self._chunks.add(chunk))

        logger.info(
            "knowledge_article_ingested",
            source_ref=source_ref,
            title=title,
            chunk_count=len(stored),
        )
        return {
            "source_ref": source_ref,
            "title": title,
            "chunk_count": len(stored),
            "chunk_ids": [str(c.id) for c in stored],
        }

    async def delete_article(self, *, source_ref: str) -> dict[str, Any]:
        """Delete all chunks for a knowledge article by source_ref."""
        count = await self._chunks.delete_by_source_ref(source_ref)
        if count == 0:
            raise NotFoundError(f"No chunks found for source_ref '{source_ref}'")
        logger.info("knowledge_article_deleted", source_ref=source_ref, chunk_count=count)
        return {"source_ref": source_ref, "deleted_chunk_count": count}

    async def get_article_chunks(self, *, source_ref: str) -> list[dict[str, Any]]:
        """List all chunks for a knowledge article by source_ref."""
        rows = await self._chunks.get_by_source_ref(source_ref)
        return [
            {
                "id": str(c.id),
                "source_ref": c.source_ref,
                "title": c.title,
                "content": c.content,
                "embedding_model_version": c.embedding_model_version,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in rows
        ]

    async def list_articles(self, *, offset: int = 0, limit: int = 50) -> list[dict[str, Any]]:
        """List distinct knowledge articles (grouped by source_ref)."""
        rows = await self._chunks.list_distinct_articles(offset=offset, limit=limit)
        return [
            {
                "source_ref": row["source_ref"],
                "title": row["title"],
                "chunk_count": row["chunk_count"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
            for row in rows
        ]
