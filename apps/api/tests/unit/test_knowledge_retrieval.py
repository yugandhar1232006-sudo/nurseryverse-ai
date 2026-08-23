"""
Unit tests for `KnowledgeRetrievalService` -- the query-time half of the
AI Assistant's RAG integration. Per the class's own docstring, `retrieve()`
must NEVER raise: no provider configured, an unreachable/erroring embedding
API, or a malformed response all degrade to `[]` rather than failing the
whole Assistant turn. The embedding provider is injected as a mock, matching
this codebase's established convention for isolating third-party network
calls.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from app.ai.assistant.embedding_providers import EmbeddingProvider
from app.ai.assistant.knowledge_retrieval import KnowledgeRetrievalService
from app.core.config import Settings
from app.models.ai import KnowledgeBaseChunk

pytestmark = pytest.mark.unit


def _chunk(*, nursery_id: uuid.UUID | None, source_type: str, embedding: list[float], content: str = "chunk") -> KnowledgeBaseChunk:
    return KnowledgeBaseChunk(
        id=uuid.uuid4(), nursery_id=nursery_id, source_type=source_type, source_ref=None, title=None,
        content=content, embedding=embedding, embedding_model_version="test-embedding-model",
    )


def _fake_embedding_provider(*, embedding: list[float] | None = None, side_effect: Exception | None = None) -> AsyncMock:
    provider = AsyncMock(spec=EmbeddingProvider)
    provider.is_configured.return_value = True
    if side_effect is not None:
        provider.embed.side_effect = side_effect
    elif embedding is not None:
        provider.embed.return_value = embedding
    return provider


class TestNoProviderConfigured:
    async def test_returns_empty_list_without_making_any_embedding_call(self, harness):
        provider = _fake_embedding_provider()
        provider.is_configured.return_value = False
        service = KnowledgeRetrievalService(
            settings=Settings(_env_file=None, APP_ENV="test", EMBEDDING_PROVIDER="ollama"),
            chunk_repo=harness.knowledge_base_chunks,
            embedding_provider=provider,
        )

        result = await service.retrieve(query="how do I care for a fig?", nursery_id=uuid.uuid4())

        assert result == []
        provider.embed.assert_not_awaited()


class TestSuccessfulRetrieval:
    async def test_returns_the_nearest_chunks_for_the_tenant(self, harness):
        nursery_id = uuid.uuid4()
        query_embedding = [1.0, 0.0, 0.0]
        close_chunk = await harness.knowledge_base_chunks.add(
            _chunk(nursery_id=nursery_id, source_type="org_data", embedding=[0.9, 0.1, 0.0], content="close match")
        )
        await harness.knowledge_base_chunks.add(
            _chunk(nursery_id=nursery_id, source_type="org_data", embedding=[0.0, 1.0, 0.0], content="far match")
        )
        other_tenant_chunk = await harness.knowledge_base_chunks.add(
            _chunk(nursery_id=uuid.uuid4(), source_type="org_data", embedding=[1.0, 0.0, 0.0], content="other tenant")
        )
        provider = _fake_embedding_provider(embedding=query_embedding)
        service = KnowledgeRetrievalService(
            settings=Settings(_env_file=None, APP_ENV="test", EMBEDDING_PROVIDER="ollama"),
            chunk_repo=harness.knowledge_base_chunks,
            embedding_provider=provider,
        )

        result = await service.retrieve(query="how do I care for a fig?", nursery_id=nursery_id)

        result_ids = [c.id for c in result]
        assert close_chunk.id in result_ids
        assert other_tenant_chunk.id not in result_ids
        assert result_ids[0] == close_chunk.id  # closest cosine match ranked first

    async def test_includes_global_knowledge_articles_regardless_of_tenant(self, harness):
        nursery_id = uuid.uuid4()
        article = await harness.knowledge_base_chunks.add(
            _chunk(nursery_id=None, source_type="knowledge_article", embedding=[1.0, 0.0, 0.0])
        )
        provider = _fake_embedding_provider(embedding=[1.0, 0.0, 0.0])
        service = KnowledgeRetrievalService(
            settings=Settings(_env_file=None, APP_ENV="test", EMBEDDING_PROVIDER="ollama"),
            chunk_repo=harness.knowledge_base_chunks,
            embedding_provider=provider,
        )

        result = await service.retrieve(query="general care question", nursery_id=nursery_id)

        assert article.id in [c.id for c in result]


class TestGracefulDegradation:
    async def test_returns_empty_list_when_embedding_provider_errors(self, harness):
        import httpx
        provider = _fake_embedding_provider(side_effect=httpx.HTTPError("embedding service error"))
        service = KnowledgeRetrievalService(
            settings=Settings(_env_file=None, APP_ENV="test", EMBEDDING_PROVIDER="ollama"),
            chunk_repo=harness.knowledge_base_chunks,
            embedding_provider=provider,
        )

        result = await service.retrieve(query="anything", nursery_id=uuid.uuid4())

        assert result == []

    async def test_returns_empty_list_when_the_knowledge_base_is_simply_empty(self, harness):
        """The documented gap: no ingestion pipeline exists yet, so a real, successful embedding call against an empty table returns []."""
        provider = _fake_embedding_provider(embedding=[1.0, 0.0, 0.0])
        service = KnowledgeRetrievalService(
            settings=Settings(_env_file=None, APP_ENV="test", EMBEDDING_PROVIDER="ollama"),
            chunk_repo=harness.knowledge_base_chunks,
            embedding_provider=provider,
        )

        result = await service.retrieve(query="anything", nursery_id=uuid.uuid4())

        assert result == []
