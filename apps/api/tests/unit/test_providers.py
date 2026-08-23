"""
Tests for LLM and embedding providers -- both the Ollama providers
(unit tests with mocked HTTP + real integration tests against the
local Ollama server) and the Anthropic provider normalization logic.

Integration tests hit the real Ollama server (llama3.2 for chat,
mxbai-embed-large for embeddings) and are skipped if Ollama is not
reachable, matching this codebase's convention for optional external
service tests.
"""
from __future__ import annotations

import json
import uuid

import httpx
import pytest

from app.ai.assistant.embedding_providers import OllamaEmbeddingProvider
from app.ai.assistant.providers import (
    ChatResponse,
    OllamaProvider,
    _to_anthropic_messages,
    _to_ollama_tool,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Anthropic message conversion
# ---------------------------------------------------------------------------


class TestToAnthropicMessages:
    def test_simple_user_assistant_exchange(self):
        messages = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
        ]
        result = _to_anthropic_messages(messages)
        assert result == [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
        ]

    def test_assistant_tool_calls_become_content_blocks(self):
        tool_id = str(uuid.uuid4())
        messages = [
            {"role": "user", "content": "What is plant 123?"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": tool_id, "type": "function", "function": {"name": "get_plant_summary", "arguments": {"plant_id": "123"}}}
                ],
            },
        ]
        result = _to_anthropic_messages(messages)
        assert len(result) == 2  # user + assistant
        assert result[1]["role"] == "assistant"
        blocks = result[1]["content"]
        assert len(blocks) == 1
        assert blocks[0]["type"] == "tool_use"
        assert blocks[0]["name"] == "get_plant_summary"
        assert blocks[0]["id"] == tool_id

    def test_tool_results_become_user_tool_result_message(self):
        tool_id = str(uuid.uuid4())
        messages = [
            {"role": "user", "content": "What is plant 123?"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": tool_id, "type": "function", "function": {"name": "get_plant_summary", "arguments": {"plant_id": "123"}}}]},
            {"role": "tool", "tool_call_id": tool_id, "content": json.dumps({"plant_id": "123", "status": "healthy"})},
        ]
        result = _to_anthropic_messages(messages)
        assert len(result) == 3
        # The tool result becomes a user message with tool_result blocks
        assert result[2]["role"] == "user"
        assert result[2]["content"][0]["type"] == "tool_result"
        assert result[2]["content"][0]["tool_use_id"] == tool_id
        assert result[2]["content"][0]["is_error"] is False

    def test_error_tool_result_is_flagged(self):
        tool_id = str(uuid.uuid4())
        messages = [
            {"role": "tool", "tool_call_id": tool_id, "content": json.dumps({"error": "not found"})},
        ]
        result = _to_anthropic_messages(messages)
        assert result[0]["content"][0]["is_error"] is True

    def test_multiple_tool_results_are_grouped(self):
        id1, id2 = str(uuid.uuid4()), str(uuid.uuid4())
        messages = [
            {"role": "tool", "tool_call_id": id1, "content": '{"ok": true}'},
            {"role": "tool", "tool_call_id": id2, "content": '{"ok": true}'},
        ]
        result = _to_anthropic_messages(messages)
        assert len(result) == 1  # grouped into one user message
        assert len(result[0]["content"]) == 2


class TestToOllamaTool:
    def test_converts_anthropic_tool_def_to_openai_format(self):
        tool_def = {
            "name": "get_plant_summary",
            "description": "Get plant info",
            "input_schema": {"type": "object", "properties": {"plant_id": {"type": "string"}}},
        }
        result = _to_ollama_tool(tool_def)
        assert result == {
            "type": "function",
            "function": {
                "name": "get_plant_summary",
                "description": "Get plant info",
                "parameters": {"type": "object", "properties": {"plant_id": {"type": "string"}}},
            },
        }


# ---------------------------------------------------------------------------
# Ollama provider unit tests (mocked HTTP)
# ---------------------------------------------------------------------------


class TestOllamaProviderUnit:
    def test_is_configured_always_returns_true(self):
        provider = OllamaProvider()
        assert provider.is_configured() is True

    def test_normalize_simple_text_response(self):
        data = {
            "message": {"role": "assistant", "content": "Hello!"},
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": 50,
            "eval_count": 20,
        }
        result = OllamaProvider._normalize(data, "llama3.2")
        assert result.content == "Hello!"
        assert result.tool_calls == []
        assert result.stop_reason == "end_turn"
        assert result.input_tokens == 50
        assert result.output_tokens == 20

    def test_normalize_tool_call_response(self):
        data = {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_abc",
                        "function": {"name": "get_plant_summary", "arguments": {"plant_id": "123"}},
                    }
                ],
            },
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": 100,
            "eval_count": 30,
        }
        result = OllamaProvider._normalize(data, "llama3.2")
        assert result.content is None
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "get_plant_summary"
        assert result.tool_calls[0].arguments == {"plant_id": "123"}
        assert result.stop_reason == "tool_use"

    def test_normalize_generates_id_when_missing(self):
        data = {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"function": {"name": "test", "arguments": {}}}
                ],
            },
            "done": True,
        }
        result = OllamaProvider._normalize(data, "llama3.2")
        assert result.tool_calls[0].id  # auto-generated UUID

    def test_normalize_empty_content(self):
        data = {"message": {"role": "assistant", "content": None}, "done": True, "prompt_eval_count": 10, "eval_count": 5}
        result = OllamaProvider._normalize(data, "llama3.2")
        assert result.content is None


# ---------------------------------------------------------------------------
# Ollama provider integration tests (real Ollama server)
# ---------------------------------------------------------------------------


def _ollama_reachable() -> bool:
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
        return r.status_code == 200
    except httpx.HTTPError:
        return False


@pytest.mark.integration
@pytest.mark.skipif(not _ollama_reachable(), reason="Ollama server not reachable")
class TestOllamaProviderIntegration:
    async def test_simple_text_completion(self):
        provider = OllamaProvider()
        response = await provider.chat(
            messages=[{"role": "user", "content": "Say exactly one word: hello"}],
            system="You are a helpful assistant.",
            tools=[],
            model="llama3.2",
            max_tokens=50,
        )
        assert isinstance(response, ChatResponse)
        assert response.content is not None
        assert response.input_tokens > 0
        assert response.output_tokens > 0

    async def test_tool_calling(self):
        provider = OllamaProvider()
        tool_def = {
            "name": "get_weather",
            "description": "Get the weather for a location",
            "input_schema": {"type": "object", "properties": {"location": {"type": "string"}}, "required": ["location"]},
        }
        response = await provider.chat(
            messages=[{"role": "user", "content": "What is the weather in London?"}],
            system="You are a helpful assistant. Use the get_weather tool.",
            tools=[tool_def],
            model="llama3.2",
            max_tokens=200,
        )
        assert isinstance(response, ChatResponse)
        # llama3.2 with tools should return tool_calls
        assert len(response.tool_calls) >= 1
        assert response.tool_calls[0].name == "get_weather"
        assert "location" in response.tool_calls[0].arguments


@pytest.mark.integration
@pytest.mark.skipif(not _ollama_reachable(), reason="Ollama server not reachable")
class TestOllamaEmbeddingIntegration:
    async def test_embedding_returns_correct_dimension(self):
        provider = OllamaEmbeddingProvider()
        embedding = await provider.embed("How do I care for a fig plant?")
        assert isinstance(embedding, list)
        assert len(embedding) == 1024  # mxbai-embed-large dimension
        assert all(isinstance(x, float) for x in embedding)

    async def test_embedding_produces_different_vectors_for_different_texts(self):
        provider = OllamaEmbeddingProvider()
        e1 = await provider.embed("How to water plants")
        e2 = await provider.embed("Revenue forecasting methods")
        assert e1 != e2

    async def test_embedding_produces_similar_vectors_for_similar_texts(self):
        provider = OllamaEmbeddingProvider()
        e1 = await provider.embed("How do I water a fig plant?")
        e2 = await provider.embed("Watering instructions for fig trees")
        # Cosine similarity should be high for similar texts
        dot = sum(a * b for a, b in zip(e1, e2))
        norm1 = sum(a * a for a in e1) ** 0.5
        norm2 = sum(b * b for b in e2) ** 0.5
        similarity = dot / (norm1 * norm2)
        assert similarity > 0.5  # reasonable threshold for similar topics
