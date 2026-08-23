"""
Unit tests for the RAG ingestion pipeline: `KnowledgeArticleService`
and the `chunk_text` helper.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from app.ai.assistant.embedding_providers import EmbeddingProvider
from app.core.config import Settings
from app.core.exceptions import NotFoundError, ValidationError
from app.models.ai import KnowledgeBaseChunk
from app.services.knowledge_article_service import KnowledgeArticleService, chunk_text

pytestmark = pytest.mark.unit

_EMBEDDING_DIM = 1024


def _make_embedding(*, value: float = 0.5) -> list[float]:
    return [value] * _EMBEDDING_DIM


def _fake_embedding_provider(*, embedding: list[float] | None = None, side_effect: Exception | None = None) -> AsyncMock:
    provider = AsyncMock(spec=EmbeddingProvider)
    provider.is_configured.return_value = True
    if side_effect is not None:
        provider.embed.side_effect = side_effect
    elif embedding is not None:
        provider.embed.return_value = embedding
    return provider


def _settings(**overrides) -> Settings:
    defaults = {
        "EMBEDDING_PROVIDER": "ollama",
        "OLLAMA_BASE_URL": "http://localhost:11434",
        "VOYAGE_API_KEY": "",
    }
    defaults.update(overrides)
    return Settings(**defaults)


# ==========================================================================
# chunk_text unit tests
# ==========================================================================


class TestChunkText:
    def test_single_short_paragraph(self):
        result = chunk_text("Hello world.")
        assert result == ["Hello world."]

    def test_multiple_paragraphs(self):
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        result = chunk_text(text)
        assert len(result) == 3
        assert result[0] == "First paragraph."
        assert result[1] == "Second paragraph."
        assert result[2] == "Third paragraph."

    def test_long_paragraph_splits_on_sentences(self):
        # Create a paragraph longer than max_chars
        sentences = [f"Sentence {i}." for i in range(20)]
        text = " ".join(sentences)
        result = chunk_text(text, max_chars=100)
        assert len(result) > 1
        for chunk in result:
            assert len(chunk) <= 100

    def test_empty_paragraphs_are_skipped(self):
        text = "\n\n\n\nHello.\n\n\n\nWorld."
        result = chunk_text(text)
        assert len(result) == 2
        assert result[0] == "Hello."
        assert result[1] == "World."

    def test_whitespace_is_stripped(self):
        text = "  Hello.  \n\n  World.  "
        result = chunk_text(text)
        assert result[0] == "Hello."
        assert result[1] == "World."

    def test_empty_input(self):
        assert chunk_text("") == []

    def test_only_whitespace(self):
        assert chunk_text("   \n\n   ") == []


# ==========================================================================
# KnowledgeArticleService unit tests (mocked repository)
# ==========================================================================


class TestKnowledgeArticleService:
    """Tests using an in-memory FakeKnowledgeBaseChunkRepository."""

    async def test_create_article_stores_chunks(self):
        from tests.fakes.repositories import FakeKnowledgeBaseChunkRepository

        provider = _fake_embedding_provider(embedding=_make_embedding())
        repo = FakeKnowledgeBaseChunkRepository()
        service = KnowledgeArticleService(
            settings=_settings(), chunk_repo=repo, embedding_provider=provider,
        )

        result = await service.create_article(
            title="Ficus Care",
            content="Keep in indirect light.\n\nWater weekly.",
            source_ref="species:ficus-lyrata",
        )

        assert result["chunk_count"] == 2
        assert result["source_ref"] == "species:ficus-lyrata"
        assert len(result["chunk_ids"]) == 2
        assert provider.embed.call_count == 2

    async def test_create_article_idempotent_on_source_ref(self):
        from tests.fakes.repositories import FakeKnowledgeBaseChunkRepository

        provider = _fake_embedding_provider(embedding=_make_embedding())
        repo = FakeKnowledgeBaseChunkRepository()
        service = KnowledgeArticleService(
            settings=_settings(), chunk_repo=repo, embedding_provider=provider,
        )

        await service.create_article(
            title="Ficus Care v1",
            content="First version.",
            source_ref="species:ficus",
        )
        assert len(repo.chunks) == 1

        await service.create_article(
            title="Ficus Care v2",
            content="Second version with more detail.\n\nNew paragraph.",
            source_ref="species:ficus",
        )
        # Old chunk deleted, new chunks created
        assert len(repo.chunks) == 2
        titles = [c.title for c in repo.chunks.values()]
        assert all("v2" in t or "part" in t for t in titles)

    async def test_create_article_empty_content_raises(self):
        from tests.fakes.repositories import FakeKnowledgeBaseChunkRepository

        provider = _fake_embedding_provider(embedding=_make_embedding())
        repo = FakeKnowledgeBaseChunkRepository()
        service = KnowledgeArticleService(
            settings=_settings(), chunk_repo=repo, embedding_provider=provider,
        )

        with pytest.raises(ValidationError, match="no chunks"):
            await service.create_article(
                title="Empty", content="", source_ref="test:empty",
            )

    async def test_create_article_embedding_failure_raises(self):
        from tests.fakes.repositories import FakeKnowledgeBaseChunkRepository

        import httpx
        provider = _fake_embedding_provider(side_effect=httpx.ConnectError("Ollama down"))
        repo = FakeKnowledgeBaseChunkRepository()
        service = KnowledgeArticleService(
            settings=_settings(), chunk_repo=repo, embedding_provider=provider,
        )

        with pytest.raises(ValidationError, match="Failed to embed"):
            await service.create_article(
                title="Fail", content="Some content.", source_ref="test:fail",
            )

    async def test_create_article_wrong_dimension_raises(self):
        from tests.fakes.repositories import FakeKnowledgeBaseChunkRepository

        provider = _fake_embedding_provider(embedding=[0.1] * 512)  # Wrong dim
        repo = FakeKnowledgeBaseChunkRepository()
        service = KnowledgeArticleService(
            settings=_settings(), chunk_repo=repo, embedding_provider=provider,
        )

        with pytest.raises(ValidationError, match="dimension mismatch"):
            await service.create_article(
                title="Bad Dim", content="Some content.", source_ref="test:dim",
            )

    async def test_delete_article_removes_chunks(self):
        from tests.fakes.repositories import FakeKnowledgeBaseChunkRepository

        provider = _fake_embedding_provider(embedding=_make_embedding())
        repo = FakeKnowledgeBaseChunkRepository()
        service = KnowledgeArticleService(
            settings=_settings(), chunk_repo=repo, embedding_provider=provider,
        )

        await service.create_article(
            title="To Delete", content="Content.\n\nMore.", source_ref="test:delete",
        )
        assert len(repo.chunks) == 2

        result = await service.delete_article(source_ref="test:delete")
        assert result["deleted_chunk_count"] == 2
        assert len(repo.chunks) == 0

    async def test_delete_nonexistent_article_raises(self):
        from tests.fakes.repositories import FakeKnowledgeBaseChunkRepository

        repo = FakeKnowledgeBaseChunkRepository()
        service = KnowledgeArticleService(
            settings=_settings(), chunk_repo=repo,
        )

        with pytest.raises(NotFoundError):
            await service.delete_article(source_ref="nonexistent")

    async def test_unconfigured_provider_raises(self):
        from tests.fakes.repositories import FakeKnowledgeBaseChunkRepository

        provider = _fake_embedding_provider()
        provider.is_configured.return_value = False
        repo = FakeKnowledgeBaseChunkRepository()
        service = KnowledgeArticleService(
            settings=_settings(), chunk_repo=repo, embedding_provider=provider,
        )

        with pytest.raises(ValidationError, match="not configured"):
            await service.create_article(
                title="No Provider", content="Content.", source_ref="test:no-provider",
            )
