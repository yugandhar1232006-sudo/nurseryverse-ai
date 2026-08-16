"""
Unit tests for `KnowledgeRetrievalService` -- the query-time half of the
AI Assistant's RAG integration. Per the class's own docstring, `retrieve()`
must NEVER raise: no API key, an unreachable/erroring Voyage API, or a
malformed response all degrade to `[]` (no retrieved context) rather than
failing the whole Assistant turn. The real Voyage HTTP call is patched at
the `httpx.AsyncClient` boundary (this codebase's established convention
for isolating third-party network calls, restated in
`test_assistant_orchestrator.py`'s own module docstring) -- everything
else (the embedding-failure branching, the repository call) is real.
"""
from __future__ import annotations

import uuid

import httpx
import pytest

from app.ai.assistant.knowledge_retrieval import KnowledgeRetrievalService
from app.core.config import Settings
from app.models.ai import KnowledgeBaseChunk

pytestmark = pytest.mark.unit


class _FakeAsyncClient:
    """Stands in for `httpx.AsyncClient` as an async context manager -- `post()` either returns a canned response or raises a canned exception, matching the real client's shape closely enough for the service's own `async with ... as client: await client.post(...)` usage."""

    def __init__(self, *, response: httpx.Response | None = None, exception: Exception | None = None) -> None:
        self._response = response
        self._exception = exception

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *exc_info: object) -> bool:
        return False

    async def post(self, url: str, **kwargs: object) -> httpx.Response:
        if self._exception is not None:
            raise self._exception
        assert self._response is not None
        return self._response


def _voyage_success_response(embedding: list[float]) -> httpx.Response:
    request = httpx.Request("POST", "https://api.voyageai.com/v1/embeddings")
    return httpx.Response(200, request=request, json={"data": [{"embedding": embedding}]})


def _voyage_error_response(status_code: int) -> httpx.Response:
    request = httpx.Request("POST", "https://api.voyageai.com/v1/embeddings")
    return httpx.Response(status_code, request=request, json={"error": "rate limited"})


def _chunk(*, nursery_id: uuid.UUID | None, source_type: str, embedding: list[float], content: str = "chunk") -> KnowledgeBaseChunk:
    return KnowledgeBaseChunk(
        id=uuid.uuid4(), nursery_id=nursery_id, source_type=source_type, source_ref=None, title=None,
        content=content, embedding=embedding, embedding_model_version="voyage-3",
    )


class TestNoApiKeyConfigured:
    async def test_returns_empty_list_without_making_any_http_call(self, harness):
        service = KnowledgeRetrievalService(
            settings=Settings(_env_file=None, APP_ENV="test", VOYAGE_API_KEY=""), chunk_repo=harness.knowledge_base_chunks
        )

        result = await service.retrieve(query="how do I care for a fig?", nursery_id=uuid.uuid4())

        assert result == []


class TestSuccessfulRetrieval:
    async def test_returns_the_nearest_chunks_for_the_tenant(self, harness, monkeypatch):
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
        service = KnowledgeRetrievalService(
            settings=Settings(_env_file=None, APP_ENV="test", VOYAGE_API_KEY="voyage-test-key"),
            chunk_repo=harness.knowledge_base_chunks,
        )
        fake_client = _FakeAsyncClient(response=_voyage_success_response(query_embedding))
        monkeypatch.setattr(
            "app.ai.assistant.knowledge_retrieval.httpx.AsyncClient", lambda **kwargs: fake_client
        )

        result = await service.retrieve(query="how do I care for a fig?", nursery_id=nursery_id)

        result_ids = [c.id for c in result]
        assert close_chunk.id in result_ids
        assert other_tenant_chunk.id not in result_ids
        assert result_ids[0] == close_chunk.id  # closest cosine match ranked first

    async def test_includes_global_knowledge_articles_regardless_of_tenant(self, harness, monkeypatch):
        nursery_id = uuid.uuid4()
        article = await harness.knowledge_base_chunks.add(
            _chunk(nursery_id=None, source_type="knowledge_article", embedding=[1.0, 0.0, 0.0])
        )
        service = KnowledgeRetrievalService(
            settings=Settings(_env_file=None, APP_ENV="test", VOYAGE_API_KEY="voyage-test-key"),
            chunk_repo=harness.knowledge_base_chunks,
        )
        fake_client = _FakeAsyncClient(response=_voyage_success_response([1.0, 0.0, 0.0]))
        monkeypatch.setattr(
            "app.ai.assistant.knowledge_retrieval.httpx.AsyncClient", lambda **kwargs: fake_client
        )

        result = await service.retrieve(query="general care question", nursery_id=nursery_id)

        assert article.id in [c.id for c in result]


class TestGracefulDegradation:
    async def test_returns_empty_list_when_voyage_api_errors(self, harness, monkeypatch):
        service = KnowledgeRetrievalService(
            settings=Settings(_env_file=None, APP_ENV="test", VOYAGE_API_KEY="voyage-test-key"),
            chunk_repo=harness.knowledge_base_chunks,
        )
        fake_client = _FakeAsyncClient(response=_voyage_error_response(500))
        monkeypatch.setattr(
            "app.ai.assistant.knowledge_retrieval.httpx.AsyncClient", lambda **kwargs: fake_client
        )

        result = await service.retrieve(query="anything", nursery_id=uuid.uuid4())

        assert result == []

    async def test_returns_empty_list_when_voyage_is_unreachable(self, harness, monkeypatch):
        service = KnowledgeRetrievalService(
            settings=Settings(_env_file=None, APP_ENV="test", VOYAGE_API_KEY="voyage-test-key"),
            chunk_repo=harness.knowledge_base_chunks,
        )
        fake_client = _FakeAsyncClient(exception=httpx.ConnectError("connection refused"))
        monkeypatch.setattr(
            "app.ai.assistant.knowledge_retrieval.httpx.AsyncClient", lambda **kwargs: fake_client
        )

        result = await service.retrieve(query="anything", nursery_id=uuid.uuid4())

        assert result == []

    async def test_returns_empty_list_for_a_malformed_response_body(self, harness, monkeypatch):
        service = KnowledgeRetrievalService(
            settings=Settings(_env_file=None, APP_ENV="test", VOYAGE_API_KEY="voyage-test-key"),
            chunk_repo=harness.knowledge_base_chunks,
        )
        request = httpx.Request("POST", "https://api.voyageai.com/v1/embeddings")
        malformed = httpx.Response(200, request=request, json={"unexpected": "shape"})
        fake_client = _FakeAsyncClient(response=malformed)
        monkeypatch.setattr(
            "app.ai.assistant.knowledge_retrieval.httpx.AsyncClient", lambda **kwargs: fake_client
        )

        result = await service.retrieve(query="anything", nursery_id=uuid.uuid4())

        assert result == []

    async def test_returns_empty_list_when_the_knowledge_base_is_simply_empty(self, harness, monkeypatch):
        """The documented, honest gap: no ingestion pipeline exists yet, so a real, successful embedding call against an empty table still returns []."""
        service = KnowledgeRetrievalService(
            settings=Settings(_env_file=None, APP_ENV="test", VOYAGE_API_KEY="voyage-test-key"),
            chunk_repo=harness.knowledge_base_chunks,
        )
        fake_client = _FakeAsyncClient(response=_voyage_success_response([1.0, 0.0, 0.0]))
        monkeypatch.setattr(
            "app.ai.assistant.knowledge_retrieval.httpx.AsyncClient", lambda **kwargs: fake_client
        )

        result = await service.retrieve(query="anything", nursery_id=uuid.uuid4())

        assert result == []
