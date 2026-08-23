"""
Knowledge article management API routes (RAG Ingestion Pipeline).

Provides CRUD endpoints for curated platform-wide horticultural knowledge
articles. Articles are chunked, embedded via the configured EmbeddingProvider,
and stored in `knowledge_base_chunks` for similarity search by the AI
Assistant's RAG retrieval pipeline.

All routes require `admin:manage` permission, matching the platform-wide
AI administration pattern established by `app/api/routes/admin.py`'s
Section 10 routes.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import (
    get_current_user,
    get_knowledge_article_service,
    require_permission,
)
from app.core.exceptions import NotFoundError
from app.core.responses import ErrorResponse
from app.models.identity import User
from app.schemas.ai import (
    CreateKnowledgeArticleRequest,
    KnowledgeArticleDetailResponse,
    KnowledgeArticleIngestResponse,
    KnowledgeArticleResponse,
    UpdateKnowledgeArticleRequest,
)
from app.services.authorization_service import AuthorizationDecision
from app.services.knowledge_article_service import KnowledgeArticleService

router = APIRouter(prefix="/ai/knowledge-articles")

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication failed"},
    403: {"model": ErrorResponse, "description": "Missing permission or cross-tenant access"},
}


@router.post(
    "",
    response_model=KnowledgeArticleIngestResponse,
    responses=_ERROR_RESPONSES,
    summary="Create (or re-create) a knowledge article in the RAG knowledge base",
)
async def create_knowledge_article(
    request: CreateKnowledgeArticleRequest,
    service: KnowledgeArticleService = Depends(get_knowledge_article_service),
    _decision: AuthorizationDecision = Depends(require_permission("admin:manage")),
    _user: User = Depends(get_current_user),
) -> KnowledgeArticleIngestResponse:
    result = await service.create_article(
        title=request.title,
        content=request.content,
        source_ref=request.source_ref,
        tags=request.tags,
    )
    return KnowledgeArticleIngestResponse(**result)


@router.get(
    "",
    response_model=list[KnowledgeArticleResponse],
    responses=_ERROR_RESPONSES,
    summary="List knowledge articles in the RAG knowledge base",
)
async def list_knowledge_articles(
    offset: int = 0,
    limit: int = 50,
    service: KnowledgeArticleService = Depends(get_knowledge_article_service),
    _decision: AuthorizationDecision = Depends(require_permission("admin:read")),
    _user: User = Depends(get_current_user),
) -> list[KnowledgeArticleResponse]:
    articles = await service.list_articles(offset=offset, limit=limit)
    return [KnowledgeArticleResponse(**a) for a in articles]


@router.get(
    "/{source_ref}",
    response_model=KnowledgeArticleDetailResponse,
    responses=_ERROR_RESPONSES,
    summary="Get a knowledge article's chunks",
)
async def get_knowledge_article(
    source_ref: str,
    service: KnowledgeArticleService = Depends(get_knowledge_article_service),
    _decision: AuthorizationDecision = Depends(require_permission("admin:read")),
    _user: User = Depends(get_current_user),
) -> KnowledgeArticleDetailResponse:
    chunks = await service.get_article_chunks(source_ref=source_ref)
    title = chunks[0]["title"] if chunks else None
    return KnowledgeArticleDetailResponse(
        source_ref=source_ref,
        title=title,
        chunk_count=len(chunks),
        chunks=chunks,
    )


@router.put(
    "/{source_ref}",
    response_model=KnowledgeArticleIngestResponse,
    responses=_ERROR_RESPONSES,
    summary="Re-ingest a knowledge article (replaces all chunks)",
)
async def update_knowledge_article(
    source_ref: str,
    request: UpdateKnowledgeArticleRequest,
    service: KnowledgeArticleService = Depends(get_knowledge_article_service),
    _decision: AuthorizationDecision = Depends(require_permission("admin:manage")),
    _user: User = Depends(get_current_user),
) -> KnowledgeArticleIngestResponse:
    existing_chunks = await service.get_article_chunks(source_ref=source_ref)
    if not existing_chunks:
        raise NotFoundError(f"Knowledge article '{source_ref}' not found")

    existing_title = existing_chunks[0].get("title", source_ref)
    existing_content = "\n\n".join(c["content"] for c in existing_chunks)

    title = request.title if request.title is not None else existing_title
    content = request.content if request.content is not None else existing_content

    result = await service.create_article(
        title=title,
        content=content,
        source_ref=source_ref,
        tags=request.tags,
    )
    return KnowledgeArticleIngestResponse(**result)


@router.delete(
    "/{source_ref}",
    responses=_ERROR_RESPONSES,
    summary="Delete a knowledge article from the RAG knowledge base",
)
async def delete_knowledge_article(
    source_ref: str,
    service: KnowledgeArticleService = Depends(get_knowledge_article_service),
    _decision: AuthorizationDecision = Depends(require_permission("admin:manage")),
    _user: User = Depends(get_current_user),
) -> dict:
    return await service.delete_article(source_ref=source_ref)
