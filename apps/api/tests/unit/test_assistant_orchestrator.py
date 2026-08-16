"""
Unit tests for `AssistantOrchestrator`. Per this codebase's established
testing convention for third-party network SDKs (see `email_sender.py`'s
own docstring: unit tests patch `smtplib.SMTP` -- isolating a third-party
network call, not our business logic), these tests patch
`anthropic.AsyncAnthropic` at the SDK boundary rather than hitting a real
API. `unittest.mock.AsyncMock` stands in for the client; fake response
objects (`SimpleNamespace`) mimic the SDK's `Message`/content-block/
`Usage` shapes closely enough for the orchestrator's own attribute
access (`.content`, `.stop_reason`, `.usage.input_tokens`, block `.type`/
`.text`/`.id`/`.name`/`.input`) to work unmodified.
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import anthropic
import httpx
import pytest

from app.ai.assistant.orchestrator import AssistantOrchestrator
from app.core.config import Settings
from app.core.exceptions import ModelUnavailableError

pytestmark = pytest.mark.unit


def _settings(**overrides) -> Settings:
    defaults = {"_env_file": None, "APP_ENV": "test", "ANTHROPIC_API_KEY": "test-key-123"}
    defaults.update(overrides)
    return Settings(**defaults)


def _text_message(text: str, *, input_tokens: int = 100, output_tokens: int = 20) -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason="end_turn",
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


def _tool_use_message(
    *, tool_name: str, tool_input: dict, tool_use_id: str | None = None, input_tokens: int = 100, output_tokens: int = 20
) -> SimpleNamespace:
    return SimpleNamespace(
        content=[
            SimpleNamespace(type="tool_use", id=tool_use_id or str(uuid.uuid4()), name=tool_name, input=tool_input)
        ],
        stop_reason="tool_use",
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


def _fake_tool_registry(*, invoke_result=None) -> SimpleNamespace:
    registry = SimpleNamespace()
    registry.tool_definitions = lambda: [{"name": "get_plant_summary", "description": "...", "input_schema": {}}]
    registry.invoke = AsyncMock(return_value=invoke_result or {"ok": True})
    return registry


def _request() -> httpx.Request:
    return httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def _response(status_code: int) -> httpx.Response:
    return httpx.Response(status_code, request=_request())


class TestNoApiKeyConfigured:
    async def test_raises_model_unavailable_without_ever_constructing_a_client(self):
        orchestrator = AssistantOrchestrator(settings=_settings(ANTHROPIC_API_KEY=""))
        registry = _fake_tool_registry()

        with patch("app.ai.assistant.orchestrator.anthropic.AsyncAnthropic") as mock_cls:
            with pytest.raises(ModelUnavailableError):
                await orchestrator.run_turn(
                    history=[{"role": "user", "content": "hi"}], tools=registry, system_prompt="You are helpful."
                )
            mock_cls.assert_not_called()


class TestSimpleTextTurn:
    async def test_returns_text_response_with_token_totals_and_cost(self):
        orchestrator = AssistantOrchestrator(settings=_settings())
        registry = _fake_tool_registry()
        mock_client = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock(return_value=_text_message(
            "Your fig plant looks healthy.", input_tokens=1000, output_tokens=500
        ))))

        with patch("app.ai.assistant.orchestrator.anthropic.AsyncAnthropic", return_value=mock_client):
            result = await orchestrator.run_turn(
                history=[{"role": "user", "content": "How is my fig plant?"}],
                tools=registry, system_prompt="You are helpful.",
            )

        assert result.content == "Your fig plant looks healthy."
        assert result.input_tokens == 1000
        assert result.output_tokens == 500
        assert result.proposed_action is None
        assert result.tool_calls_made == []
        # (1000/1e6 * 3.00) + (500/1e6 * 15.00) = 0.003 + 0.0075 = 0.0105
        assert result.cost_usd == Decimal("0.010500")


class TestToolCallingLoop:
    async def test_calls_a_read_tool_then_returns_the_final_text_answer(self):
        orchestrator = AssistantOrchestrator(settings=_settings())
        registry = _fake_tool_registry(invoke_result={"common_label": "Fig #1", "status": "healthy"})
        first = _tool_use_message(tool_name="get_plant_summary", tool_input={"plant_id": str(uuid.uuid4())})
        second = _text_message("Fig #1 is currently healthy.")
        mock_client = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock(side_effect=[first, second])))

        with patch("app.ai.assistant.orchestrator.anthropic.AsyncAnthropic", return_value=mock_client):
            result = await orchestrator.run_turn(
                history=[{"role": "user", "content": "How is Fig #1?"}],
                tools=registry, system_prompt="You are helpful.",
            )

        assert result.content == "Fig #1 is currently healthy."
        assert result.tool_calls_made == ["get_plant_summary"]
        assert result.input_tokens == 200  # summed across both calls
        registry.invoke.assert_awaited_once()

    async def test_a_write_tool_proposal_ends_the_turn_immediately_without_executing(self):
        orchestrator = AssistantOrchestrator(settings=_settings())
        plant_id = str(uuid.uuid4())
        registry = _fake_tool_registry(
            invoke_result={
                "requires_confirmation": True,
                "tool_name": "propose_watering_log",
                "tool_arguments": {"plant_id": plant_id, "volume_ml": 200},
                "summary": "Record a watering event for plant Fig #1 (200 mL).",
            }
        )
        response = _tool_use_message(tool_name="propose_watering_log", tool_input={"plant_id": plant_id, "volume_ml": 200})
        mock_client = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock(return_value=response)))

        with patch("app.ai.assistant.orchestrator.anthropic.AsyncAnthropic", return_value=mock_client):
            result = await orchestrator.run_turn(
                history=[{"role": "user", "content": "Log that I watered Fig #1 with 200mL."}],
                tools=registry, system_prompt="You are helpful.",
            )

        assert result.proposed_action is not None
        assert result.proposed_action.tool_name == "propose_watering_log"
        assert result.proposed_action.tool_arguments["volume_ml"] == 200
        assert result.content == "Record a watering event for plant Fig #1 (200 mL)."
        # Only ONE API call was made -- the turn ended at the proposal, no further round-trip.
        mock_client.messages.create.assert_awaited_once()

    async def test_a_denied_write_tool_call_is_reported_back_to_the_model_not_ended(self):
        """
        Authorization failures (`{"error": "..."}`, no `requires_confirmation`
        key) are relayed to the model as a tool_result so it can explain the
        denial in plain language -- the turn continues, it doesn't silently
        stop the way a genuine proposal does.
        """
        orchestrator = AssistantOrchestrator(settings=_settings())
        registry = _fake_tool_registry(invoke_result={"error": "You do not have permission to record watering."})
        first = _tool_use_message(tool_name="propose_watering_log", tool_input={"plant_id": str(uuid.uuid4())})
        second = _text_message("I wasn't able to do that -- you don't have permission to record watering.")
        mock_client = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock(side_effect=[first, second])))

        with patch("app.ai.assistant.orchestrator.anthropic.AsyncAnthropic", return_value=mock_client):
            result = await orchestrator.run_turn(
                history=[{"role": "user", "content": "Log watering for that plant."}],
                tools=registry, system_prompt="You are helpful.",
            )

        assert result.proposed_action is None
        assert "permission" in result.content.lower()
        assert mock_client.messages.create.await_count == 2

    async def test_max_tool_iterations_exceeded_returns_a_friendly_fallback_not_an_error(self):
        orchestrator = AssistantOrchestrator(settings=_settings(ASSISTANT_MAX_TOOL_ITERATIONS=2))
        registry = _fake_tool_registry(invoke_result={"ok": True})
        # Every response keeps requesting another tool call -- the loop never terminates on its own.
        always_tool_use = _tool_use_message(tool_name="get_plant_summary", tool_input={"plant_id": str(uuid.uuid4())})
        mock_client = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock(return_value=always_tool_use)))

        with patch("app.ai.assistant.orchestrator.anthropic.AsyncAnthropic", return_value=mock_client):
            result = await orchestrator.run_turn(
                history=[{"role": "user", "content": "Tell me everything."}],
                tools=registry, system_prompt="You are helpful.",
            )

        assert result.proposed_action is None
        assert "narrow down" in result.content.lower() or "ask again" in result.content.lower()
        assert mock_client.messages.create.await_count == 2  # exactly ASSISTANT_MAX_TOOL_ITERATIONS


class TestRetryAndFailover:
    async def test_retries_a_transient_error_then_succeeds(self):
        orchestrator = AssistantOrchestrator(settings=_settings())
        registry = _fake_tool_registry()
        transient = anthropic.APIConnectionError(request=_request())
        success = _text_message("All good now.")
        mock_client = SimpleNamespace(
            messages=SimpleNamespace(create=AsyncMock(side_effect=[transient, success]))
        )

        with patch("app.ai.assistant.orchestrator.anthropic.AsyncAnthropic", return_value=mock_client), \
                patch("app.ai.assistant.orchestrator.asyncio.sleep", new=AsyncMock()) as mock_sleep:
            result = await orchestrator.run_turn(
                history=[{"role": "user", "content": "hi"}], tools=registry, system_prompt="You are helpful."
            )

        assert result.content == "All good now."
        mock_sleep.assert_awaited_once()

    async def test_raises_model_unavailable_after_retries_are_exhausted(self):
        orchestrator = AssistantOrchestrator(settings=_settings())
        registry = _fake_tool_registry()
        overloaded = anthropic.OverloadedError(message="overloaded", response=_response(529), body=None)
        mock_client = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock(side_effect=overloaded)))

        with patch("app.ai.assistant.orchestrator.anthropic.AsyncAnthropic", return_value=mock_client), \
                patch("app.ai.assistant.orchestrator.asyncio.sleep", new=AsyncMock()):
            with pytest.raises(ModelUnavailableError):
                await orchestrator.run_turn(
                    history=[{"role": "user", "content": "hi"}], tools=registry, system_prompt="You are helpful."
                )

        assert mock_client.messages.create.await_count == 3  # _MAX_RETRIES=2 -> 3 total attempts

    async def test_non_retryable_api_error_fails_fast_without_retrying(self):
        orchestrator = AssistantOrchestrator(settings=_settings())
        registry = _fake_tool_registry()
        bad_request = anthropic.BadRequestError(message="invalid request", response=_response(400), body=None)
        mock_client = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock(side_effect=bad_request)))

        with patch("app.ai.assistant.orchestrator.anthropic.AsyncAnthropic", return_value=mock_client), \
                patch("app.ai.assistant.orchestrator.asyncio.sleep", new=AsyncMock()) as mock_sleep:
            with pytest.raises(ModelUnavailableError):
                await orchestrator.run_turn(
                    history=[{"role": "user", "content": "hi"}], tools=registry, system_prompt="You are helpful."
                )

        assert mock_client.messages.create.await_count == 1  # no retry attempted
        mock_sleep.assert_not_awaited()
