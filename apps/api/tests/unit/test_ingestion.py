"""
Unit tests for the RAG ingestion Celery task.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.ai.assistant.ingestion import _ingest_article_async

pytestmark = pytest.mark.unit


class TestIngestArticleAsync:
    """Tests for the async ingestion implementation."""

    async def test_ingest_delegates_to_service(self):
        mock_service = AsyncMock()
        mock_service.create_article.return_value = {
            "source_ref": "test:article",
            "title": "Test Article",
            "chunk_count": 2,
            "chunk_ids": ["id-1", "id-2"],
        }

        mock_session = AsyncMock()

        with (
            patch("app.ai.assistant.ingestion._build_service", return_value=mock_service),
            patch("app.ai.assistant.ingestion.AsyncSessionLocal") as mock_session_factory,
        ):
            mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await _ingest_article_async(
                settings=AsyncMock(),
                source_ref="test:article",
                title="Test Article",
                content="Some content.",
            )

        assert result["source_ref"] == "test:article"
        assert result["chunk_count"] == 2
        mock_service.create_article.assert_called_once_with(
            title="Test Article",
            content="Some content.",
            source_ref="test:article",
        )
        mock_session.commit.assert_called_once()

    async def test_ingest_rolls_back_on_error(self):
        mock_service = AsyncMock()
        mock_service.create_article.side_effect = RuntimeError("Embedding failed")

        mock_session = AsyncMock()

        with (
            patch("app.ai.assistant.ingestion._build_service", return_value=mock_service),
            patch("app.ai.assistant.ingestion.AsyncSessionLocal") as mock_session_factory,
        ):
            mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(RuntimeError, match="Embedding failed"):
                await _ingest_article_async(
                    settings=AsyncMock(),
                    source_ref="test:fail",
                    title="Fail",
                    content="Content.",
                )

        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()
