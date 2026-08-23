"""
RAG ingestion Celery task for knowledge articles.

Embeds article content using the configured EmbeddingProvider (Ollama or
Voyage AI) and stores the resulting vector chunks in `knowledge_base_chunks`
for similarity search by `KnowledgeRetrievalService`.

This task reuses `KnowledgeArticleService.create_article` under the hood,
constructing the same dependency graph `app/workers.py` builds for its
own tasks: a fresh `AsyncSession`, a `SqlAlchemyKnowledgeBaseChunkRepository`,
and the configured embedding provider. The task is idempotent on `source_ref`:
re-running for the same article replaces old chunks rather than duplicating.
"""
from __future__ import annotations

import asyncio
from typing import Any

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.repositories.sqlalchemy_repositories import SqlAlchemyKnowledgeBaseChunkRepository
from app.services.knowledge_article_service import KnowledgeArticleService

logger = get_logger(__name__)


def _build_service(settings: Settings, db) -> KnowledgeArticleService:
    chunk_repo = SqlAlchemyKnowledgeBaseChunkRepository(db)
    return KnowledgeArticleService(settings=settings, chunk_repo=chunk_repo)


async def _ingest_article_async(
    *,
    settings: Settings,
    source_ref: str,
    title: str,
    content: str,
) -> dict[str, Any]:
    """Async implementation of article ingestion, called from the sync Celery task."""
    async with AsyncSessionLocal() as db:
        try:
            service = _build_service(settings, db)
            result = await service.create_article(
                title=title,
                content=content,
                source_ref=source_ref,
            )
            await db.commit()
            logger.info(
                "ingest_article_completed",
                source_ref=source_ref,
                title=title,
                chunk_count=result["chunk_count"],
            )
            return result
        except Exception:
            await db.rollback()
            raise


def ingest_knowledge_article(
    source_ref: str,
    title: str,
    content: str,
) -> dict[str, Any]:
    """
    Synchronous Celery task entry point. Delegates to the async
    implementation via `asyncio.run()`, matching the pattern in
    `app/workers.py`.
    """
    settings = get_settings()
    return asyncio.run(
        _ingest_article_async(
            settings=settings,
            source_ref=source_ref,
            title=title,
            content=content,
        )
    )
