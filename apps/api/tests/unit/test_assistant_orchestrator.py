"""
Unit tests for `AssistantOrchestrator`. Per the provider abstraction design,
these tests inject a mock `LLMProvider` rather than patching the Anthropic
SDK at the boundary -- isolating the orchestrator's own tool-calling loop
logic from any specific provider. Provider-specific retry/error behavior is
tested in the provider tests (test_providers.py).
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.ai.assistant.orchestrator import AssistantOrchestrator
from app.ai.assistant.providers import ChatResponse, LLMProvider, ToolCall
from app.core.config import Settings
from app.core.exceptions import ModelUnavailableError

pytestmark = pytest.mark.unit


def _settings(**overrides) -> Settings:
    defaults = {
        "_env_file": None,
        "APP_ENV": "test",
        "LLM_PROVIDER": "anthropic",
        "ANTHROPIC_API_KEY": "test-key-123",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _text_response(text: str, *, input_tokens: int = 100, output_tokens: int = 20) -> ChatResponse:
    return ChatResponse(
        content=text,
        tool_calls=[],
        stop_reason="end_turn",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def _tool_use_response(
    *, tool_name: str, tool_input: dict, tool_id: str | None = None,
    input_tokens: int = 100, output_tokens: int = 20,
) -> ChatResponse:
    return ChatResponse(
        content=None,
        tool_calls=[ToolCall(id=tool_id or str(uuid.uuid4()), name=tool_name, arguments=tool_input)],
        stop_reason="tool_use",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def _fake_provider(*, side_effect=None) -> LLMProvider:
    provider = AsyncMock(spec=LLMProvider)
    provider.is_configured.return_value = True
    if side_effect is not None:
        provider.chat.side_effect = side_effect
    return provider


def _fake_tool_registry(*, invoke_result=None) -> AsyncMock:
    registry = AsyncMock()
    registry.tool_definitions.return_value = [{"name": "get_plant_summary", "description": "...", "input_schema": {}}]
    registry.invoke = AsyncMock(return_value=invoke_result or {"ok": True})
    return registry


class TestNoProviderConfigured:
    async def test_raises_model_unavailable_when_provider_not_configured(self):
        provider = _fake_provider()
        provider.is_configured.return_value = False
        orchestrator = AssistantOrchestrator(settings=_settings(), provider=provider)
        registry = _fake_tool_registry()

        with pytest.raises(ModelUnavailableError):
            await orchestrator.run_turn(
                history=[{"role": "user", "content": "hi"}], tools=registry, system_prompt="You are helpful."
            )
        provider.chat.assert_not_awaited()


class TestSimpleTextTurn:
    async def test_returns_text_response_with_token_totals_and_zero_cost_for_ollama(self):
        settings = _settings(LLM_PROVIDER="ollama", OLLAMA_CHAT_MODEL="llama3.2")
        provider = _fake_provider()
        provider.chat.return_value = _text_response(
            "Your fig plant looks healthy.", input_tokens=1000, output_tokens=500
        )
        orchestrator = AssistantOrchestrator(settings=settings, provider=provider)
        registry = _fake_tool_registry()

        result = await orchestrator.run_turn(
            history=[{"role": "user", "content": "How is my fig plant?"}],
            tools=registry, system_prompt="You are helpful.",
        )

        assert result.content == "Your fig plant looks healthy."
        assert result.input_tokens == 1000
        assert result.output_tokens == 500
        assert result.proposed_action is None
        assert result.tool_calls_made == []
        # Local Ollama: zero cost
        assert result.cost_usd == Decimal("0.000000")

    async def test_returns_text_response_with_anthropic_cost(self):
        settings = _settings(LLM_PROVIDER="anthropic", ANTHROPIC_API_KEY="test-key")
        provider = _fake_provider()
        provider.chat.return_value = _text_response(
            "Your fig plant looks healthy.", input_tokens=1000, output_tokens=500
        )
        orchestrator = AssistantOrchestrator(settings=settings, provider=provider)
        registry = _fake_tool_registry()

        result = await orchestrator.run_turn(
            history=[{"role": "user", "content": "How is my fig plant?"}],
            tools=registry, system_prompt="You are helpful.",
        )

        # (1000/1e6 * 3.00) + (500/1e6 * 15.00) = 0.003 + 0.0075 = 0.0105
        assert result.cost_usd == Decimal("0.010500")


class TestToolCallingLoop:
    async def test_calls_a_read_tool_then_returns_the_final_text_answer(self):
        provider = _fake_provider(side_effect=[
            _tool_use_response(tool_name="get_plant_summary", tool_input={"plant_id": str(uuid.uuid4())}),
            _text_response("Fig #1 is currently healthy."),
        ])
        orchestrator = AssistantOrchestrator(settings=_settings(), provider=provider)
        registry = _fake_tool_registry(invoke_result={"common_label": "Fig #1", "status": "healthy"})

        result = await orchestrator.run_turn(
            history=[{"role": "user", "content": "How is Fig #1?"}],
            tools=registry, system_prompt="You are helpful.",
        )

        assert result.content == "Fig #1 is currently healthy."
        assert result.tool_calls_made == ["get_plant_summary"]
        assert result.input_tokens == 200  # summed across both calls
        registry.invoke.assert_awaited_once()

    async def test_a_write_tool_proposal_ends_the_turn_immediately_without_executing(self):
        plant_id = str(uuid.uuid4())
        provider = _fake_provider(side_effect=[
            _tool_use_response(tool_name="propose_watering_log", tool_input={"plant_id": plant_id, "volume_ml": 200}),
        ])
        orchestrator = AssistantOrchestrator(settings=_settings(), provider=provider)
        registry = _fake_tool_registry(
            invoke_result={
                "requires_confirmation": True,
                "tool_name": "propose_watering_log",
                "tool_arguments": {"plant_id": plant_id, "volume_ml": 200},
                "summary": "Record a watering event for plant Fig #1 (200 mL).",
            }
        )

        result = await orchestrator.run_turn(
            history=[{"role": "user", "content": "Log that I watered Fig #1 with 200mL."}],
            tools=registry, system_prompt="You are helpful.",
        )

        assert result.proposed_action is not None
        assert result.proposed_action.tool_name == "propose_watering_log"
        assert result.proposed_action.tool_arguments["volume_ml"] == 200
        assert result.content == "Record a watering event for plant Fig #1 (200 mL)."
        # Only ONE API call -- the turn ended at the proposal.
        provider.chat.assert_awaited_once()

    async def test_a_denied_write_tool_call_is_reported_back_to_the_model_not_ended(self):
        provider = _fake_provider(side_effect=[
            _tool_use_response(tool_name="propose_watering_log", tool_input={"plant_id": str(uuid.uuid4())}),
            _text_response("I wasn't able to do that -- you don't have permission to record watering."),
        ])
        orchestrator = AssistantOrchestrator(settings=_settings(), provider=provider)
        registry = _fake_tool_registry(invoke_result={"error": "You do not have permission to record watering."})

        result = await orchestrator.run_turn(
            history=[{"role": "user", "content": "Log watering for that plant."}],
            tools=registry, system_prompt="You are helpful.",
        )

        assert result.proposed_action is None
        assert "permission" in result.content.lower()
        assert provider.chat.await_count == 2

    async def test_max_tool_iterations_exceeded_returns_a_friendly_fallback(self):
        settings = _settings(ASSISTANT_MAX_TOOL_ITERATIONS=2)
        always_tool_use = _tool_use_response(tool_name="get_plant_summary", tool_input={"plant_id": str(uuid.uuid4())})
        provider = _fake_provider(side_effect=[always_tool_use, always_tool_use])
        orchestrator = AssistantOrchestrator(settings=settings, provider=provider)
        registry = _fake_tool_registry(invoke_result={"ok": True})

        result = await orchestrator.run_turn(
            history=[{"role": "user", "content": "Tell me everything."}],
            tools=registry, system_prompt="You are helpful.",
        )

        assert result.proposed_action is None
        assert "narrow down" in result.content.lower() or "ask again" in result.content.lower()
        assert provider.chat.await_count == 2


class TestRetryAndFailover:
    async def test_propagates_model_unavailable_from_provider(self):
        provider = _fake_provider(side_effect=ModelUnavailableError("provider down"))
        orchestrator = AssistantOrchestrator(settings=_settings(), provider=provider)
        registry = _fake_tool_registry()

        with pytest.raises(ModelUnavailableError, match="provider down"):
            await orchestrator.run_turn(
                history=[{"role": "user", "content": "hi"}], tools=registry, system_prompt="You are helpful."
            )
