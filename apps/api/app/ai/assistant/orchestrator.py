"""
`AssistantOrchestrator` -- the AI tool-calling loop behind FR-9.1/FR-9.2
(docs/architecture/06-ai-architecture.md) with a pluggable LLM provider
abstraction supporting both Anthropic Claude and local Ollama.

PROVIDER ABSTRACTION: the orchestrator accepts an `LLMProvider` (from
`app.ai.assistant.providers`) and builds all messages in a normalized
OpenAI-compatible format (`{"role": ..., "content": ..., "tool_calls": ...}`).
Each provider is responsible for translating to/from its native API format
internally, keeping this class provider-agnostic.

ERROR HANDLING: every path that can fail -- missing API key, the provider
being unreachable, rate-limited, or erroring after retries -- raises the
typed `ModelUnavailableError` (503). Local Ollama with zero config cost is
the default provider; Anthropic requires a valid API key.

CONFIRMATION GATE (FR-9.3): if the model calls a write tool
(`AssistantToolRegistry.WRITE_TOOLS`), the loop stops immediately and
returns the proposal without executing it or making any further API
calls -- the human must confirm via `AssistantConversationService.
confirm_action` (which calls `AssistantToolRegistry.execute_confirmed_
action` directly, bypassing this orchestrator entirely) before anything
is written.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.ai.assistant.providers import LLMProvider
from app.ai.assistant.tool_registry import WRITE_TOOLS, AssistantToolRegistry
from app.core.config import Settings
from app.core.exceptions import ModelUnavailableError
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ProposedAction:
    """Mirrors `AIAssistantMessage.proposed_action`'s JSON shape exactly."""

    tool_name: str
    tool_arguments: dict[str, Any]
    summary: str


@dataclass(frozen=True)
class AssistantTurnResult:
    """
    One full turn's outcome -- from the caller's first message through
    however many read-tool round-trips the model made, ending either in a
    final text reply or a pending write-tool proposal. Token/cost totals
    are summed across every API call this turn made.
    """

    content: str
    model_name: str
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    proposed_action: ProposedAction | None = None
    tool_calls_made: list[str] = field(default_factory=list)


class AssistantOrchestrator:
    def __init__(self, *, settings: Settings, provider: LLMProvider | None = None) -> None:
        self._settings = settings
        self._provider = provider

    def _resolve_provider(self) -> LLMProvider:
        """Lazily resolve the provider from settings if not injected."""
        if self._provider is not None:
            return self._provider
        from app.ai.assistant.providers import AnthropicProvider, OllamaProvider

        if self._settings.LLM_PROVIDER == "ollama":
            return OllamaProvider(base_url=self._settings.OLLAMA_BASE_URL)
        return AnthropicProvider(api_key=self._settings.ANTHROPIC_API_KEY)

    def _resolve_model(self) -> str:
        if self._settings.LLM_PROVIDER == "ollama":
            return self._settings.OLLAMA_CHAT_MODEL
        return self._settings.ANTHROPIC_MODEL

    async def run_turn(
        self,
        *,
        history: list[dict[str, Any]],
        tools: AssistantToolRegistry,
        system_prompt: str,
    ) -> AssistantTurnResult:
        """
        `history` is the full message list for this conversation,
        INCLUDING the new user message the caller just appended.

        `system_prompt` is built by the caller (`AssistantConversationService`).

        Messages are built in normalized OpenAI-compatible format internally;
        the provider translates to its native API format.
        """
        provider = self._resolve_provider()
        model = self._resolve_model()

        if not provider.is_configured():
            provider_name = self._settings.LLM_PROVIDER
            raise ModelUnavailableError(
                f"The AI Assistant is not configured (no {provider_name} provider available)."
            )

        messages: list[dict[str, Any]] = list(history)
        tool_definitions = tools.tool_definitions()

        total_input_tokens = 0
        total_output_tokens = 0
        tool_calls_made: list[str] = []

        for iteration in range(self._settings.ASSISTANT_MAX_TOOL_ITERATIONS):
            response = await provider.chat(
                messages=messages,
                system=system_prompt,
                tools=tool_definitions,
                model=model,
                max_tokens=self._settings.ASSISTANT_MAX_TOKENS,
            )
            total_input_tokens += response.input_tokens
            total_output_tokens += response.output_tokens

            if response.stop_reason != "tool_use":
                return AssistantTurnResult(
                    content=response.content or "",
                    model_name=model,
                    input_tokens=total_input_tokens,
                    output_tokens=total_output_tokens,
                    cost_usd=self._cost(total_input_tokens, total_output_tokens),
                    tool_calls_made=tool_calls_made,
                )

            # stop_reason == "tool_use": the model wants to call one or more
            # tools.  A write-tool proposal ends the whole turn immediately
            # (FR-9.3) even if other tool calls were also present.
            # Append the assistant message with tool_calls to history.
            assistant_msg: dict[str, Any] = {"role": "assistant", "content": response.content or ""}
            if response.tool_calls:
                assistant_msg["tool_calls"] = [
                    {"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": tc.arguments}}
                    for tc in response.tool_calls
                ]
            messages.append(assistant_msg)

            for tc in response.tool_calls:
                tool_calls_made.append(tc.name)

                if tc.name in WRITE_TOOLS:
                    result = await tools.invoke(tc.name, tc.arguments)
                    if result.get("requires_confirmation"):
                        return AssistantTurnResult(
                            content=result.get("summary", "I've prepared an action for your confirmation."),
                            model_name=model,
                            input_tokens=total_input_tokens,
                            output_tokens=total_output_tokens,
                            cost_usd=self._cost(total_input_tokens, total_output_tokens),
                            proposed_action=ProposedAction(
                                tool_name=result["tool_name"],
                                tool_arguments=result["tool_arguments"],
                                summary=result["summary"],
                            ),
                            tool_calls_made=tool_calls_made,
                        )
                    # Authorization failed -- relay denial to model as a
                    # tool result so it can explain in plain language.
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result, default=str),
                    })
                    continue

                result = await tools.invoke(tc.name, tc.arguments)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, default=str),
                })

        # Exhausted max iterations -- friendly fallback, not a provider error.
        logger.warning(
            "assistant_max_tool_iterations_exceeded",
            iterations=self._settings.ASSISTANT_MAX_TOOL_ITERATIONS,
            tool_calls_made=tool_calls_made,
        )
        return AssistantTurnResult(
            content=(
                "I wasn't able to finish gathering the information needed to answer that within this turn's tool-call "
                "limit. Could you narrow down the question, or ask again?"
            ),
            model_name=model,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            cost_usd=self._cost(total_input_tokens, total_output_tokens),
            tool_calls_made=tool_calls_made,
        )

    def _cost(self, input_tokens: int, output_tokens: int) -> Decimal:
        # Local Ollama inference: zero cost.  Anthropic: per-token rates.
        if self._settings.LLM_PROVIDER == "ollama":
            return Decimal("0.000000")
        input_cost = (
            Decimal(input_tokens) / Decimal(1_000_000)
            * Decimal(str(self._settings.ANTHROPIC_INPUT_COST_PER_MTOK))
        )
        output_cost = (
            Decimal(output_tokens) / Decimal(1_000_000)
            * Decimal(str(self._settings.ANTHROPIC_OUTPUT_COST_PER_MTOK))
        )
        return (input_cost + output_cost).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
