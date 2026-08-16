"""
Unit tests for `AssistantConversationService` -- conversation persistence,
history assembly, and the FR-9.3 confirmation gate. `AssistantOrchestrator.
run_turn` is stubbed out (an `AsyncMock`) here since it has its own
dedicated, fully-mocked-at-the-SDK-boundary test file
(`test_assistant_orchestrator.py`) -- these tests are about what this
service does with an orchestrator result, not the Anthropic call itself
(which would also just raise `ModelUnavailableError` unconditionally in
this sandbox, since no `ANTHROPIC_API_KEY` is configured for tests).
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.ai.assistant.orchestrator import AssistantTurnResult, ProposedAction
from app.core.exceptions import ConflictError, NotFoundError, ValidationError

pytestmark = pytest.mark.unit


def _text_turn_result(content: str = "Here's what I found.") -> AssistantTurnResult:
    return AssistantTurnResult(
        content=content, model_name="claude-sonnet-4-5-20250929", input_tokens=100, output_tokens=40,
        cost_usd=Decimal("0.000900"),
    )


def _proposal_turn_result() -> AssistantTurnResult:
    return AssistantTurnResult(
        content="Record a watering event for plant Fig #1 (200 mL).",
        model_name="claude-sonnet-4-5-20250929", input_tokens=120, output_tokens=30, cost_usd=Decimal("0.000810"),
        proposed_action=ProposedAction(
            tool_name="propose_watering_log",
            tool_arguments={"plant_id": str(uuid.uuid4()), "volume_ml": 200},
            summary="Record a watering event for plant Fig #1 (200 mL).",
        ),
    )


class TestSendMessage:
    async def test_creates_a_new_conversation_on_first_message(self, harness):
        user = await harness.create_user(email=f"{uuid.uuid4()}@example.com")
        nursery_id = uuid.uuid4()
        harness.assistant_orchestrator.run_turn = AsyncMock(return_value=_text_turn_result())
        before = len(harness.domain_events.events)

        assistant_message = await harness.assistant_conversation_service.send_message(
            user=user, nursery_id=nursery_id, role_code="grower", conversation_id=None,
            content="How is my fig plant doing?", tool_registry=SimpleNamespace(), request_id="req-1",
        )

        assert assistant_message.role == "assistant"
        assert assistant_message.content == "Here's what I found."
        assert assistant_message.action_status is None
        events = harness.domain_events.events[before:]
        event_types = [e.event_type for e in events]
        assert "ai_assistant.conversation_started" in event_types
        assert event_types.count("ai_assistant.message_sent") == 2  # one user, one assistant

    async def test_raises_validation_error_for_empty_content(self, harness):
        user = await harness.create_user(email=f"{uuid.uuid4()}@example.com")
        harness.assistant_orchestrator.run_turn = AsyncMock(return_value=_text_turn_result())

        with pytest.raises(ValidationError):
            await harness.assistant_conversation_service.send_message(
                user=user, nursery_id=uuid.uuid4(), role_code="grower", conversation_id=None,
                content="   ", tool_registry=SimpleNamespace(), request_id=None,
            )

    async def test_reuses_an_existing_owned_conversation(self, harness):
        user = await harness.create_user(email=f"{uuid.uuid4()}@example.com")
        nursery_id = uuid.uuid4()
        harness.assistant_orchestrator.run_turn = AsyncMock(return_value=_text_turn_result("First reply."))
        first = await harness.assistant_conversation_service.send_message(
            user=user, nursery_id=nursery_id, role_code="grower", conversation_id=None,
            content="Hello", tool_registry=SimpleNamespace(), request_id=None,
        )

        harness.assistant_orchestrator.run_turn = AsyncMock(return_value=_text_turn_result("Second reply."))
        second = await harness.assistant_conversation_service.send_message(
            user=user, nursery_id=nursery_id, role_code="grower", conversation_id=first.conversation_id,
            content="Follow-up question", tool_registry=SimpleNamespace(), request_id=None,
        )

        assert second.conversation_id == first.conversation_id
        messages, total = await harness.ai_assistant_messages.list_for_conversation(
            first.conversation_id, offset=0, limit=10
        )
        assert total == 4  # user1, assistant1, user2, assistant2

    async def test_raises_not_found_for_a_conversation_owned_by_another_user(self, harness):
        owner = await harness.create_user(email=f"{uuid.uuid4()}@example.com")
        intruder = await harness.create_user(email=f"{uuid.uuid4()}@example.com")
        nursery_id = uuid.uuid4()
        harness.assistant_orchestrator.run_turn = AsyncMock(return_value=_text_turn_result())
        owned = await harness.assistant_conversation_service.send_message(
            user=owner, nursery_id=nursery_id, role_code="grower", conversation_id=None,
            content="Hello", tool_registry=SimpleNamespace(), request_id=None,
        )

        with pytest.raises(NotFoundError):
            await harness.assistant_conversation_service.send_message(
                user=intruder, nursery_id=nursery_id, role_code="grower", conversation_id=owned.conversation_id,
                content="Let me in", tool_registry=SimpleNamespace(), request_id=None,
            )

    async def test_a_proposed_action_is_persisted_pending_confirmation_and_published(self, harness):
        user = await harness.create_user(email=f"{uuid.uuid4()}@example.com")
        nursery_id = uuid.uuid4()
        harness.assistant_orchestrator.run_turn = AsyncMock(return_value=_proposal_turn_result())
        before = len(harness.domain_events.events)

        assistant_message = await harness.assistant_conversation_service.send_message(
            user=user, nursery_id=nursery_id, role_code="grower", conversation_id=None,
            content="Log that I watered Fig #1 with 200mL.", tool_registry=SimpleNamespace(), request_id=None,
        )

        assert assistant_message.action_status == "pending_confirmation"
        assert assistant_message.proposed_action["tool_name"] == "propose_watering_log"
        events = harness.domain_events.events[before:]
        assert any(e.event_type == "ai_assistant.action_proposed" for e in events)


class TestConfirmAction:
    async def test_confirming_executes_the_tool_and_records_a_result_message(self, harness):
        user = await harness.create_user(email=f"{uuid.uuid4()}@example.com")
        nursery_id = uuid.uuid4()
        harness.assistant_orchestrator.run_turn = AsyncMock(return_value=_proposal_turn_result())
        proposal_message = await harness.assistant_conversation_service.send_message(
            user=user, nursery_id=nursery_id, role_code="grower", conversation_id=None,
            content="Log watering.", tool_registry=SimpleNamespace(), request_id=None,
        )
        fake_registry = SimpleNamespace(execute_confirmed_action=AsyncMock(return_value="Watering log recorded (id abc123)."))
        before = len(harness.domain_events.events)

        result_message = await harness.assistant_conversation_service.confirm_action(
            user=user, nursery_id=nursery_id, conversation_id=proposal_message.conversation_id,
            message_id=proposal_message.id, tool_registry=fake_registry, request_id=None,
        )

        assert result_message.content == "Watering log recorded (id abc123)."
        fake_registry.execute_confirmed_action.assert_awaited_once_with(
            tool_name="propose_watering_log", tool_arguments=proposal_message.proposed_action["tool_arguments"]
        )
        updated = await harness.ai_assistant_messages.get_by_id(proposal_message.id)
        assert updated.action_status == "confirmed"
        events = harness.domain_events.events[before:]
        assert any(e.event_type == "ai_assistant.action_confirmed" for e in events)

    async def test_confirming_an_already_confirmed_action_raises_conflict(self, harness):
        user = await harness.create_user(email=f"{uuid.uuid4()}@example.com")
        nursery_id = uuid.uuid4()
        harness.assistant_orchestrator.run_turn = AsyncMock(return_value=_proposal_turn_result())
        proposal_message = await harness.assistant_conversation_service.send_message(
            user=user, nursery_id=nursery_id, role_code="grower", conversation_id=None,
            content="Log watering.", tool_registry=SimpleNamespace(), request_id=None,
        )
        fake_registry = SimpleNamespace(execute_confirmed_action=AsyncMock(return_value="Recorded."))
        await harness.assistant_conversation_service.confirm_action(
            user=user, nursery_id=nursery_id, conversation_id=proposal_message.conversation_id,
            message_id=proposal_message.id, tool_registry=fake_registry, request_id=None,
        )

        with pytest.raises(ConflictError):
            await harness.assistant_conversation_service.confirm_action(
                user=user, nursery_id=nursery_id, conversation_id=proposal_message.conversation_id,
                message_id=proposal_message.id, tool_registry=fake_registry, request_id=None,
            )

    async def test_confirming_a_plain_text_message_raises_validation_error(self, harness):
        user = await harness.create_user(email=f"{uuid.uuid4()}@example.com")
        nursery_id = uuid.uuid4()
        harness.assistant_orchestrator.run_turn = AsyncMock(return_value=_text_turn_result())
        plain_message = await harness.assistant_conversation_service.send_message(
            user=user, nursery_id=nursery_id, role_code="grower", conversation_id=None,
            content="Just a question, no action.", tool_registry=SimpleNamespace(), request_id=None,
        )
        fake_registry = SimpleNamespace(execute_confirmed_action=AsyncMock())

        with pytest.raises(ValidationError):
            await harness.assistant_conversation_service.confirm_action(
                user=user, nursery_id=nursery_id, conversation_id=plain_message.conversation_id,
                message_id=plain_message.id, tool_registry=fake_registry, request_id=None,
            )
        fake_registry.execute_confirmed_action.assert_not_awaited()

    async def test_confirming_someone_elses_conversation_raises_not_found(self, harness):
        owner = await harness.create_user(email=f"{uuid.uuid4()}@example.com")
        intruder = await harness.create_user(email=f"{uuid.uuid4()}@example.com")
        nursery_id = uuid.uuid4()
        harness.assistant_orchestrator.run_turn = AsyncMock(return_value=_proposal_turn_result())
        proposal_message = await harness.assistant_conversation_service.send_message(
            user=owner, nursery_id=nursery_id, role_code="grower", conversation_id=None,
            content="Log watering.", tool_registry=SimpleNamespace(), request_id=None,
        )
        fake_registry = SimpleNamespace(execute_confirmed_action=AsyncMock())

        with pytest.raises(NotFoundError):
            await harness.assistant_conversation_service.confirm_action(
                user=intruder, nursery_id=nursery_id, conversation_id=proposal_message.conversation_id,
                message_id=proposal_message.id, tool_registry=fake_registry, request_id=None,
            )


class TestCancelAction:
    async def test_cancelling_discards_the_proposal_with_no_side_effect(self, harness):
        user = await harness.create_user(email=f"{uuid.uuid4()}@example.com")
        nursery_id = uuid.uuid4()
        harness.assistant_orchestrator.run_turn = AsyncMock(return_value=_proposal_turn_result())
        proposal_message = await harness.assistant_conversation_service.send_message(
            user=user, nursery_id=nursery_id, role_code="grower", conversation_id=None,
            content="Log watering.", tool_registry=SimpleNamespace(), request_id=None,
        )
        before_watering_count = len(harness.watering_logs.logs) if hasattr(harness.watering_logs, "logs") else None
        before = len(harness.domain_events.events)

        cancelled_message = await harness.assistant_conversation_service.cancel_action(
            user=user, nursery_id=nursery_id, conversation_id=proposal_message.conversation_id,
            message_id=proposal_message.id, request_id=None,
        )

        assert cancelled_message.action_status == "cancelled"
        events = harness.domain_events.events[before:]
        assert any(e.event_type == "ai_assistant.action_cancelled" for e in events)
        if before_watering_count is not None:
            assert len(harness.watering_logs.logs) == before_watering_count

    async def test_cancelling_an_already_cancelled_action_raises_conflict(self, harness):
        user = await harness.create_user(email=f"{uuid.uuid4()}@example.com")
        nursery_id = uuid.uuid4()
        harness.assistant_orchestrator.run_turn = AsyncMock(return_value=_proposal_turn_result())
        proposal_message = await harness.assistant_conversation_service.send_message(
            user=user, nursery_id=nursery_id, role_code="grower", conversation_id=None,
            content="Log watering.", tool_registry=SimpleNamespace(), request_id=None,
        )
        await harness.assistant_conversation_service.cancel_action(
            user=user, nursery_id=nursery_id, conversation_id=proposal_message.conversation_id,
            message_id=proposal_message.id, request_id=None,
        )

        with pytest.raises(ConflictError):
            await harness.assistant_conversation_service.cancel_action(
                user=user, nursery_id=nursery_id, conversation_id=proposal_message.conversation_id,
                message_id=proposal_message.id, request_id=None,
            )


class TestGetConversation:
    async def test_returns_the_conversation_and_its_messages(self, harness):
        user = await harness.create_user(email=f"{uuid.uuid4()}@example.com")
        nursery_id = uuid.uuid4()
        harness.assistant_orchestrator.run_turn = AsyncMock(return_value=_text_turn_result())
        sent = await harness.assistant_conversation_service.send_message(
            user=user, nursery_id=nursery_id, role_code="grower", conversation_id=None,
            content="Hello", tool_registry=SimpleNamespace(), request_id=None,
        )

        conversation, messages, total = await harness.assistant_conversation_service.get_conversation(
            user=user, nursery_id=nursery_id, conversation_id=sent.conversation_id, offset=0, limit=10
        )

        assert conversation.id == sent.conversation_id
        assert total == 2
        assert {m.role for m in messages} == {"user", "assistant"}

    async def test_raises_not_found_for_another_users_conversation(self, harness):
        owner = await harness.create_user(email=f"{uuid.uuid4()}@example.com")
        intruder = await harness.create_user(email=f"{uuid.uuid4()}@example.com")
        nursery_id = uuid.uuid4()
        harness.assistant_orchestrator.run_turn = AsyncMock(return_value=_text_turn_result())
        sent = await harness.assistant_conversation_service.send_message(
            user=owner, nursery_id=nursery_id, role_code="grower", conversation_id=None,
            content="Hello", tool_registry=SimpleNamespace(), request_id=None,
        )

        with pytest.raises(NotFoundError):
            await harness.assistant_conversation_service.get_conversation(
                user=intruder, nursery_id=nursery_id, conversation_id=sent.conversation_id, offset=0, limit=10
            )

    async def test_raises_not_found_for_a_conversation_in_a_different_nursery(self, harness):
        user = await harness.create_user(email=f"{uuid.uuid4()}@example.com")
        nursery_id = uuid.uuid4()
        other_nursery_id = uuid.uuid4()
        harness.assistant_orchestrator.run_turn = AsyncMock(return_value=_text_turn_result())
        sent = await harness.assistant_conversation_service.send_message(
            user=user, nursery_id=nursery_id, role_code="grower", conversation_id=None,
            content="Hello", tool_registry=SimpleNamespace(), request_id=None,
        )

        with pytest.raises(NotFoundError):
            await harness.assistant_conversation_service.get_conversation(
                user=user, nursery_id=other_nursery_id, conversation_id=sent.conversation_id, offset=0, limit=10
            )
