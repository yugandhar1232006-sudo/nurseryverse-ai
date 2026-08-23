"""
Embedding provider abstraction for the RAG knowledge base.

Two providers:

1. **VoyageEmbeddingProvider** -- the existing Voyage AI API path (`voyage-3`,
   1024 dimensions), preserving the exact HTTP call currently in
   `knowledge_retrieval.py`.

2. **OllamaEmbeddingProvider** -- uses Ollama's local `/api/embed` endpoint
   with `mxbai-embed-large` (1024 dimensions, matching `EMBEDDING_DIM` in
   `app/models/ai.py` -- no migration needed).

Both return `list[float]` via the `EmbeddingProvider.embed()` method, so
`KnowledgeRetrievalService` works identically regardless of backend.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

_REQUEST_TIMEOUT_SECONDS = 10.0


class EmbeddingProvider(ABC):
    """Protocol for embedding generation backends."""

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Return the embedding vector for the given text."""

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if this provider has what it needs to operate."""


class VoyageEmbeddingProvider(EmbeddingProvider):
    """The existing Voyage AI embeddings API path (model `voyage-3`, 1024-d)."""

    _VOYAGE_URL = "https://api.voyageai.com/v1/embeddings"
    _MODEL = "voyage-3"

    def __init__(self, *, api_key: str) -> None:
        self._api_key = api_key

    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def embed(self, text: str) -> list[float]:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.post(
                self._VOYAGE_URL,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"input": [text], "model": self._MODEL, "input_type": "query"},
            )
            response.raise_for_status()
            data = response.json()
            return [float(x) for x in data["data"][0]["embedding"]]


class OllamaEmbeddingProvider(EmbeddingProvider):
    """
    Uses Ollama's local `/api/embed` endpoint with `mxbai-embed-large`.

    Verified dimension: 1024 (matches `EMBEDDING_DIM` in app/models/ai.py).
    """

    _DEFAULT_BASE_URL = "http://localhost:11434"

    def __init__(self, *, base_url: str = _DEFAULT_BASE_URL, model: str = "mxbai-embed-large") -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model

    def is_configured(self) -> bool:
        return True

    async def embed(self, text: str) -> list[float]:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{self._base_url}/api/embed",
                json={"model": self._model, "input": text},
            )
            response.raise_for_status()
            data = response.json()
            return [float(x) for x in data["embeddings"][0]]
