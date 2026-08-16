"""
`AssistantOrchestrator` -- the real Anthropic Claude API tool-calling loop
behind FR-9.1/FR-9.2 (docs/architecture/06-ai-architecture.md §1: "Anthropic
Claude API, tool-calling"; docs/architecture/02-low-level-design.md's
"Module: AI Assistant": "AI orchestration ... streaming responses ...
tool/function calling ... provider failover/retry ... cost tracking ...
token usage analytics").

SCOPE NOTE (disclosed in full in the Module 10 completion report): the
user's Module 10 kickoff also listed "multi-model support (Claude, OpenAI,
Gemini, local models)" and "provider failover" as candidate features. This
project's own pre-existing architecture doc (docs/architecture/06-ai-
architecture.md §1) commits to a SINGLE provider -- Anthropic Claude -- for
the AI Assistant, with no multi-provider abstraction anywhere in the LLD's
"Module: AI Assistant" section. Per the user's own explicit instruction
governing this module ("Do not invent functionality outside the existing
architecture. Infer the implementation from the previous modules"), this
class implements the documented single-provider design, not a new
multi-provider SDK layer that no other module or doc anticipates. "Retry
handling" and "failover" are implemented in the one sense the existing
architecture actually specifies -- transient-error retry with backoff
against the configured provider (see `_call_with_retry` below) -- not
cross-provider failover, which the LLD does not describe.

ERROR HANDLING: every path that can fail -- missing API key, the Anthropic
API being unreachable, rate-limited, or erroring after retries -- raises
the typed `ModelUnavailableError` (503), matching this same LLD section's
own note: "LLM API failure surfaces as an inline chat error with retry,
never blocks the rest of the app." Callers (`AssistantConversationService`)
catch this exactly the way `QRService`/prediction modules already catch it
for the ML side of this bounded context -- one consistent graceful-
degradation contract across all of Module 10, not a second error shape
for the LLM half.

CONFIRMATION GATE (FR-9.3): if the model calls a write tool
(`AssistantToolRegistry.WRITE_TOOLS`), the loop stops immediately and
returns the proposal without executing it or making any further API
calls -- the human must confirm via `AssistantConversationService.
confirm_action` (which calls `AssistantToolRegistry.execute_confirmed_
action` directly, bypassing this orchestrator entirely) before anything
is written. This orchestrator itself never calls `execute_confirmed_
action`.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import anthropic

from app.ai.assistant.tool_registry import WRITE_TOOLS, AssistantToolRegistry
from app.core.config import Settings
from app.core.exceptions import ModelUnavailableError
from app.core.logging import get_logger

logger = get_logger(__name__)

# Transient, provider-side failures worth a same-provider retry before
# surfacing `ModelUnavailableError` -- rate limiting, momentary overload,
# connection blips, and Anthropic's own 5xx responses. `AuthenticationError`/
# `BadRequestError`/`PermissionDeniedError` are deliberately excluded: those
# are configuration or programming errors that a retry cannot fix, and
# retrying them would only delay the (identical) failure.
_RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    anthropic.APIConnectionError,
    anthropic.APITimeoutError,
    anthropic.RateLimitError,
    anthropic.InternalServerError,
    anthropic.OverloadedError,
)
_MAX_RETRIES = 2
_RETRY_BASE_DELAY_SECONDS = 0.5


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
    are summed across every API call this turn made (a turn with two
    read-tool round-trips makes three API calls; the persisted
    `AIAssistantMessage` row gets one combined total, matching migration
    0015's one-row-per-assistant-turn column shape).
    """

    content: str
    model_name: str
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    proposed_action: ProposedAction | None = None
    tool_calls_made: list[str] = field(default_factory=list)


class AssistantOrchestrator:
    def __init__(self, *, settings: Settings) -> None:
        self._settings = settings

    async def run_turn(
        self,
        *,
        history: list[dict[str, Any]],
        tools: AssistantToolRegistry,
        system_prompt: str,
    ) -> AssistantTurnResult:
        """
        `history` is the full Anthropic-format message list for this
        conversation, INCLUDING the new user message the caller just
        appended (`AssistantConversationService` owns building this list
        from persisted `AIAssistantMessage` rows -- this class is
        stateless between calls, matching `InferenceBase`'s own
        "assemble first, run second" boundary).

        `system_prompt` is built by the caller (`AssistantConversationService.
        _build_system_prompt`) -- docs/architecture/06-ai-architecture.md
        §7: "system prompt establishes the assistant's role, tenant
        context ... and hard constraints (never fabricate data, always
        cite the tool result a claim is based on, never execute a write
        without going through the confirmation flow)", plus any RAG
        passages that same section's retrieval step (§9) found relevant.
        This class stays tenant-context-agnostic itself (it has no
        `user`/`nursery_id` of its own) -- the caller assembles that
        context, matching every other "assemble first, run second"
        boundary in this codebase.
        """
        if not self._settings.ANTHROPIC_API_KEY:
            raise ModelUnavailableError(
                "The AI Assistant is not configured (no Anthropic API key set for this deployment)."
            )

        client = anthropic.AsyncAnthropic(api_key=self._settings.ANTHROPIC_API_KEY)
        messages: list[dict[str, Any]] = list(history)
        tool_definitions = tools.tool_definitions()

        total_input_tokens = 0
        total_output_tokens = 0
        tool_calls_made: list[str] = []

        for iteration in range(self._settings.ASSISTANT_MAX_TOOL_ITERATIONS):
            response = await self._call_with_retry(
                client=client, messages=messages, tool_definitions=tool_definitions, system_prompt=system_prompt
            )
            total_input_tokens += response.usage.input_tokens
            total_output_tokens += response.usage.output_tokens

            if response.stop_reason != "tool_use":
                text = "".join(block.text for block in response.content if block.type == "text")
                return AssistantTurnResult(
                    content=text,
                    model_name=self._settings.ANTHROPIC_MODEL,
                    input_tokens=total_input_tokens,
                    output_tokens=total_output_tokens,
                    cost_usd=self._cost(total_input_tokens, total_output_tokens),
                    tool_calls_made=tool_calls_made,
                )

            # stop_reason == "tool_use": the model wants to call one or more
            # tools. Claude may request several tool_use blocks in one
            # response; each gets its own tool_result. A write-tool proposal
            # ends the whole turn immediately (FR-9.3) even if other
            # tool_use blocks were also present in the same response.
            assistant_content = [_block_to_param(block) for block in response.content]
            messages.append({"role": "assistant", "content": assistant_content})

            tool_results: list[dict[str, Any]] = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                tool_calls_made.append(block.name)

                if block.name in WRITE_TOOLS:
                    result = await tools.invoke(block.name, block.input)
                    if result.get("requires_confirmation"):
                        return AssistantTurnResult(
                            content=result.get("summary", "I've prepared an action for your confirmation."),
                            model_name=self._settings.ANTHROPIC_MODEL,
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
                    # Authorization failed (`{"error": "..."}`) -- report the
                    # denial back to the model as a tool result rather than
                    # ending the turn, so it can relay the reason in plain
                    # language instead of the turn dying silently.
                    tool_results.append(_tool_result_param(block.id, result))
                    continue

                result = await tools.invoke(block.name, block.input)
                tool_results.append(_tool_result_param(block.id, result))

            messages.append({"role": "user", "content": tool_results})

        # Exhausted ASSISTANT_MAX_TOOL_ITERATIONS without a final answer or
        # a proposal -- an orchestration-depth limit, not a provider
        # failure, so this does NOT raise ModelUnavailableError (that's
        # reserved for the provider actually being unreachable/erroring).
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
            model_name=self._settings.ANTHROPIC_MODEL,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            cost_usd=self._cost(total_input_tokens, total_output_tokens),
            tool_calls_made=tool_calls_made,
        )

    async def _call_with_retry(
        self,
        *,
        client: anthropic.AsyncAnthropic,
        messages: list[dict[str, Any]],
        tool_definitions: list[dict[str, Any]],
        system_prompt: str,
    ) -> Any:
        last_error: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                return await client.messages.create(
                    model=self._settings.ANTHROPIC_MODEL,
                    max_tokens=self._settings.ASSISTANT_MAX_TOKENS,
                    system=system_prompt,
                    messages=messages,  # type: ignore[arg-type]  # runtime-correct Anthropic message JSON; the SDK's MessageParam TypedDicts are stricter than a dynamically-built conversation history can satisfy statically.
                    tools=tool_definitions,  # type: ignore[arg-type]  # same -- tool_definitions() builds runtime-correct Anthropic tool-use JSON schemas.
                )
            except _RETRYABLE_EXCEPTIONS as exc:
                last_error = exc
                if attempt < _MAX_RETRIES:
                    delay = _RETRY_BASE_DELAY_SECONDS * (2**attempt)
                    logger.warning(
                        "anthropic_api_retry", attempt=attempt + 1, max_retries=_MAX_RETRIES,
                        error=type(exc).__name__, delay_seconds=delay,
                    )
                    await asyncio.sleep(delay)
            except anthropic.APIError as exc:
                # Non-retryable provider error (auth, bad request, permission,
                # request-too-large, etc.) -- fail fast, no point retrying.
                logger.error("anthropic_api_error", error=type(exc).__name__, detail=str(exc))
                raise ModelUnavailableError(
                    "The AI Assistant is temporarily unavailable (the AI provider rejected the request)."
                ) from exc

        logger.error("anthropic_api_retries_exhausted", error=type(last_error).__name__ if last_error else None)
        raise ModelUnavailableError(
            "The AI Assistant is temporarily unavailable (the AI provider did not respond after retrying). Please try again shortly."
        ) from last_error

    def _cost(self, input_tokens: int, output_tokens: int) -> Decimal:
        input_cost = Decimal(input_tokens) / Decimal(1_000_000) * Decimal(str(self._settings.ANTHROPIC_INPUT_COST_PER_MTOK))
        output_cost = Decimal(output_tokens) / Decimal(1_000_000) * Decimal(str(self._settings.ANTHROPIC_OUTPUT_COST_PER_MTOK))
        return (input_cost + output_cost).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def _block_to_param(block: Any) -> dict[str, Any]:
    """Anthropic response content blocks (`TextBlock`/`ToolUseBlock`) back into the request-shaped dict Claude expects on the next call."""
    if block.type == "text":
        return {"type": "text", "text": block.text}
    if block.type == "tool_use":
        return {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
    raise ModelUnavailableError(f"The AI Assistant received an unsupported response block type ('{block.type}') from the provider.")


def _tool_result_param(tool_use_id: str, result: dict[str, Any]) -> dict[str, Any]:
    import json

    return {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "content": json.dumps(result, default=str),
        "is_error": bool(result.get("error")),
    }
