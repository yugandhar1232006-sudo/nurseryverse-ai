"""
LLM provider abstraction -- lets the Assistant work with either the real
Anthropic Claude API or a local Ollama server, selected entirely by
environment variables (no code changes needed to switch providers).

Two providers are implemented here:

1. **AnthropicProvider** -- wraps the `anthropic` SDK directly (the existing
   single-provider design, preserving all retry/cost-tracking semantics).

2. **OllamaProvider** -- talks to Ollama's OpenAI-compatible `/api/chat`
   endpoint via `httpx`, supporting tool-calling with the same tool
   definitions the orchestrator builds. Cost tracking uses zero rates (local
   inference has no per-token cost).

Both normalize their responses into `ChatResponse`, so the orchestrator's
tool-calling loop works identically regardless of which provider is active.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import anthropic
import httpx

from app.core.exceptions import ModelUnavailableError
from app.core.logging import get_logger

logger = get_logger(__name__)

# Retry constants (shared by both providers for transient-failure handling).
_MAX_RETRIES = 2
_RETRY_BASE_DELAY_SECONDS = 0.5


# ---------------------------------------------------------------------------
# Normalized response types -- both providers convert their native responses
# into these so the orchestrator's tool-calling loop is provider-agnostic.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ToolCall:
    """A single tool call requested by the model."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ChatResponse:
    """
    Provider-agnostic chat response.  The orchestrator reads *only* this,
    never the underlying Anthropic/Ollama response shapes.
    """

    content: str | None  # text content (None when the model only issued tool calls)
    tool_calls: list[ToolCall]
    stop_reason: str  # "end_turn" | "tool_use" | "max_tokens" | ...
    input_tokens: int
    output_tokens: int


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class LLMProvider(ABC):
    """Protocol that both Anthropic and Ollama providers satisfy."""

    @abstractmethod
    async def chat(
        self,
        *,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]],
        model: str,
        max_tokens: int,
    ) -> ChatResponse:
        """Send a chat completion request; return a normalized response."""

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if this provider has the credentials/endpoint it needs."""


# ---------------------------------------------------------------------------
# Anthropic provider
# ---------------------------------------------------------------------------

_ANTHROPIC_RETRYABLE: tuple[type[Exception], ...] = (
    anthropic.APIConnectionError,
    anthropic.APITimeoutError,
    anthropic.RateLimitError,
    anthropic.InternalServerError,
    anthropic.OverloadedError,
)


class AnthropicProvider(LLMProvider):
    """Wraps `anthropic.AsyncAnthropic` -- the existing single-provider path."""

    def __init__(self, *, api_key: str) -> None:
        self._api_key = api_key
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def chat(
        self,
        *,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]],
        model: str,
        max_tokens: int,
    ) -> ChatResponse:
        anthropic_msgs = _to_anthropic_messages(messages)
        raw = await self._call_with_retry(
            messages=anthropic_msgs, system=system, tools=tools, model=model, max_tokens=max_tokens,
        )
        return self._normalize(raw, model)

    async def _call_with_retry(
        self, *, messages: list[dict[str, Any]], system: str, tools: list[dict[str, Any]], model: str, max_tokens: int,
    ) -> Any:
        last_error: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                return await self._client.messages.create(
                    model=model, max_tokens=max_tokens, system=system,
                    messages=messages,  # type: ignore[arg-type]
                    tools=tools,  # type: ignore[arg-type]
                )
            except _ANTHROPIC_RETRYABLE as exc:
                last_error = exc
                if attempt < _MAX_RETRIES:
                    delay = _RETRY_BASE_DELAY_SECONDS * (2**attempt)
                    logger.warning(
                        "anthropic_api_retry", attempt=attempt + 1, max_retries=_MAX_RETRIES,
                        error=type(exc).__name__, delay_seconds=delay,
                    )
                    await asyncio.sleep(delay)
            except anthropic.APIError as exc:
                logger.error("anthropic_api_error", error=type(exc).__name__, detail=str(exc))
                raise ModelUnavailableError(
                    "The AI Assistant is temporarily unavailable (the AI provider rejected the request)."
                ) from exc
        logger.error("anthropic_api_retries_exhausted", error=type(last_error).__name__ if last_error else None)
        raise ModelUnavailableError(
            "The AI Assistant is temporarily unavailable (the AI provider did not respond after retrying)."
        ) from last_error

    @staticmethod
    def _normalize(raw: Any, model: str) -> ChatResponse:
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in raw.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, arguments=block.input))
        return ChatResponse(
            content="".join(text_parts) or None,
            tool_calls=tool_calls,
            stop_reason=raw.stop_reason,
            input_tokens=raw.usage.input_tokens,
            output_tokens=raw.usage.output_tokens,
        )


# ---------------------------------------------------------------------------
# Ollama provider
# ---------------------------------------------------------------------------


class OllamaProvider(LLMProvider):
    """
    Talks to Ollama's OpenAI-compatible `/api/chat` endpoint.

    Ollama supports tool-calling natively (tested with llama3.2), returning
    tool calls in OpenAI's `message.tool_calls` format.  The response is
    normalized into `ChatResponse` so the orchestrator doesn't need to know
    which backend served the request.
    """

    _DEFAULT_BASE_URL = "http://localhost:11434"

    def __init__(self, *, base_url: str = _DEFAULT_BASE_URL) -> None:
        self._base_url = base_url.rstrip("/")

    def is_configured(self) -> bool:
        # Ollama is "configured" if it's reachable -- we don't need an API key.
        # The actual reachability check happens at chat time; this method
        # returns True so the orchestrator doesn't block usage when no
        # ANTHROPIC_API_KEY is set.
        return True

    async def chat(
        self,
        *,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]],
        model: str,
        max_tokens: int,
    ) -> ChatResponse:
        """
        Posts to Ollama's `/api/chat` endpoint.

        Ollama's tool format matches OpenAI's (function.name, function.description,
        function.parameters), so the tool definitions can be passed through after
        wrapping in the `type: "function"` envelope.
        """
        ollama_tools = [_to_ollama_tool(t) for t in tools] if tools else []
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "system", "content": system}] + messages,
            "stream": False,
        }
        if ollama_tools:
            payload["tools"] = ollama_tools

        last_error: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    resp = await client.post(f"{self._base_url}/api/chat", json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    return self._normalize(data, model)
            except (httpx.HTTPError, KeyError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt < _MAX_RETRIES:
                    delay = _RETRY_BASE_DELAY_SECONDS * (2**attempt)
                    logger.warning(
                        "ollama_api_retry", attempt=attempt + 1, max_retries=_MAX_RETRIES,
                        error=type(exc).__name__, delay_seconds=delay,
                    )
                    await asyncio.sleep(delay)

        logger.error("ollama_api_retries_exhausted", error=type(last_error).__name__ if last_error else None)
        raise ModelUnavailableError(
            "The AI Assistant is temporarily unavailable (Ollama did not respond after retrying)."
        ) from last_error

    @staticmethod
    def _normalize(data: dict[str, Any], model: str) -> ChatResponse:
        msg = data.get("message", {})
        content = msg.get("content") or None
        raw_tool_calls = msg.get("tool_calls") or []

        tool_calls = [
            ToolCall(
                id=tc.get("id", str(uuid.uuid4())),
                name=tc["function"]["name"],
                arguments=tc["function"].get("arguments", {}),
            )
            for tc in raw_tool_calls
        ]

        # Map Ollama's done_reason to our normalized stop_reason.
        stop_reason = "tool_use" if tool_calls else "end_turn"

        prompt_eval = data.get("prompt_eval_count", 0)
        eval_count = data.get("eval_count", 0)

        return ChatResponse(
            content=content,
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            input_tokens=prompt_eval,
            output_tokens=eval_count,
        )


def _to_ollama_tool(tool_def: dict[str, Any]) -> dict[str, Any]:
    """
    Convert an Anthropic-style tool definition (used by the existing
    `AssistantToolRegistry.tool_definitions()`) into the OpenAI/Ollama
    `{"type": "function", "function": {...}}` envelope.
    """
    return {
        "type": "function",
        "function": {
            "name": tool_def["name"],
            "description": tool_def.get("description", ""),
            "parameters": tool_def.get("input_schema", {}),
        },
    }


def _to_anthropic_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Convert normalized OpenAI-compatible messages to Anthropic's expected format.

    Anthropic requires:
    - Assistant messages with tool_use to have ``content`` as a list of blocks
      (text + tool_use), not a flat string with top-level ``tool_calls``.
    - Tool results as a ``user`` message with ``content`` being a list of
      ``tool_result`` blocks, not a separate ``role="tool"`` message.
    """
    result: list[dict[str, Any]] = []

    # Group consecutive tool-result messages into the preceding assistant's
    # tool-result user message.
    pending_tool_results: list[dict[str, Any]] = []

    for msg in messages:
        role = msg.get("role", "")

        if role == "tool":
            # Accumulate tool results -- they'll be attached to a user message
            # once we see the next non-tool message (or end of list).
            pending_tool_results.append(msg)
            continue

        # If we have accumulated tool results and are now seeing a new
        # role (assistant or user), flush them as a user tool_result message.
        if pending_tool_results:
            tool_result_blocks = [
                {
                    "type": "tool_result",
                    "tool_use_id": tr["tool_call_id"],
                    "content": tr.get("content", ""),
                    "is_error": _is_error_result(tr.get("content", "")),
                }
                for tr in pending_tool_results
            ]
            result.append({"role": "user", "content": tool_result_blocks})
            pending_tool_results = []

        if role == "assistant" and "tool_calls" in msg and msg["tool_calls"]:
            # Convert OpenAI-style tool_calls to Anthropic content blocks.
            blocks: list[dict[str, Any]] = []
            if msg.get("content"):
                blocks.append({"type": "text", "text": msg["content"]})
            for tc in msg["tool_calls"]:
                func = tc.get("function", tc)
                blocks.append({
                    "type": "tool_use",
                    "id": tc.get("id", str(uuid.uuid4())),
                    "name": func["name"] if isinstance(func, dict) else tc["name"],
                    "input": func["arguments"] if isinstance(func, dict) else tc.get("arguments", {}),
                })
            result.append({"role": "assistant", "content": blocks})
        else:
            result.append(msg)

    # Flush any remaining tool results at the end.
    if pending_tool_results:
        tool_result_blocks = [
            {
                "type": "tool_result",
                "tool_use_id": tr["tool_call_id"],
                "content": tr.get("content", ""),
                "is_error": _is_error_result(tr.get("content", "")),
            }
            for tr in pending_tool_results
        ]
        result.append({"role": "user", "content": tool_result_blocks})

    return result


def _is_error_result(content: str) -> bool:
    """Check if a tool result JSON string indicates an error."""
    try:
        data = json.loads(content) if content else {}
        return bool(data.get("error"))
    except (json.JSONDecodeError, TypeError):
        return False
