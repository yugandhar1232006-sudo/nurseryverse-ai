"""
Integration tests for Module 10's `/ai/assistant/*` routes -- real HTTP
requests exercising permission gating (`ai_assistant:use` /
`ai_assistant:confirm_write`), the "no org yet" 422, cross-user
conversation ownership (404, never 403 -- see
`AssistantConversationService`'s own module docstring on why), and the
FR-9.3 confirm/cancel branches end-to-end through a real HTTP response.

`AssistantOrchestrator.run_turn` is monkeypatched to an `AsyncMock` for
every test that needs a successful assistant turn -- this sandbox has no
`ANTHROPIC_API_KEY` configured, so the real orchestrator would otherwise
always raise `ModelUnavailableError` (itself covered by its own dedicated
test below, and by `test_assistant_orchestrator.py`'s unit tests).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.ai.assistant.orchestrator import AssistantTurnResult, ProposedAction
from app.api.deps import get_current_user
from app.main import create_app
from app.models.catalog import Species
from app.models.organization import Branch
from tests.conftest import _apply_common_overrides

pytestmark = pytest.mark.integration


def _branch(*, nursery_id: uuid.UUID) -> Branch:
    now = datetime.now(timezone.utc)
    return Branch(
        id=uuid.uuid4(), nursery_id=nursery_id, name="Main", address_line1="123 St", city="Springfield",
        country="US", timezone="UTC", created_at=now, updated_at=now,
    )


def _species(*, nursery_id: uuid.UUID) -> Species:
    now = datetime.now(timezone.utc)
    return Species(
        id=uuid.uuid4(), nursery_id=nursery_id, category_id=uuid.uuid4(), common_name="Fig",
        botanical_name="Ficus lyrata", created_at=now, updated_at=now,
    )


async def _seed_plant(harness, *, org_id: uuid.UUID):
    branch = _branch(nursery_id=org_id)
    species = _species(nursery_id=org_id)
    harness.branches.branches[branch.id] = branch
    harness.species.species[species.id] = species
    plant = await harness.plant_service.register_plant(
        nursery_id=org_id, branch_id=branch.id, species_id=species.id, actor_user_id=uuid.uuid4()
    )
    return branch, plant


def _text_turn_result(content: str = "Your fig plant looks healthy.") -> AssistantTurnResult:
    return AssistantTurnResult(
        content=content, model_name="claude-sonnet-4-5-20250929", input_tokens=100, output_tokens=40,
        cost_usd=Decimal("0.000900"),
    )


def _proposal_turn_result(*, plant_id: uuid.UUID) -> AssistantTurnResult:
    return AssistantTurnResult(
        content="Record a watering event for plant Fig #1 (200 mL).",
        model_name="claude-sonnet-4-5-20250929", input_tokens=120, output_tokens=30, cost_usd=Decimal("0.000810"),
        proposed_action=ProposedAction(
            tool_name="propose_watering_log", tool_arguments={"plant_id": str(plant_id), "volume_ml": 200},
            summary="Record a watering event for plant Fig #1 (200 mL).",
        ),
    )


class TestSendMessage:
    async def test_a_user_with_no_role_assignment_at_all_is_denied(self, authenticated_client):
        """
        `require_permission("ai_assistant:use")` runs as a route-level dependency BEFORE the handler body's
        own `_require_org` check -- a brand-new user with no `RoleAssignment` yet has no granted permissions
        at all, so this is a 403 (permission denied), not the handler's own 422 ("no org membership"). Every
        `grant_role` in this codebase's test harness ties a permission grant to an org (`RoleAssignment.
        nursery_id`), so the 422 branch has no reachable test scenario through the harness as built -- this
        test instead locks in the (correct) precedence between the two checks.
        """
        ac, user = authenticated_client

        response = await ac.post("/api/v1/ai/assistant/message", json={"content": "Hello"})

        assert response.status_code == 403

    async def test_requires_ai_assistant_use_permission(self, authenticated_client, harness):
        ac, user = authenticated_client
        org_id = uuid.uuid4()
        harness.grant_role(user, org_id=org_id, role_code="grower", permission_codes=["plants:read"])

        response = await ac.post("/api/v1/ai/assistant/message", json={"content": "Hello"})

        assert response.status_code == 403

    async def test_returns_503_when_the_assistant_is_not_configured(self, authenticated_client, harness):
        """No mocked orchestrator here -- this sandbox has no ANTHROPIC_API_KEY, so the real orchestrator raises."""
        ac, user = authenticated_client
        org_id = uuid.uuid4()
        harness.grant_role(user, org_id=org_id, role_code="grower", permission_codes=["ai_assistant:use"])

        response = await ac.post("/api/v1/ai/assistant/message", json={"content": "How is my fig plant?"})

        assert response.status_code == 503

    async def test_sends_a_message_and_returns_the_assistant_reply(self, authenticated_client, harness):
        ac, user = authenticated_client
        org_id = uuid.uuid4()
        harness.grant_role(user, org_id=org_id, role_code="grower", permission_codes=["ai_assistant:use"])
        harness.assistant_orchestrator.run_turn = AsyncMock(return_value=_text_turn_result())

        response = await ac.post("/api/v1/ai/assistant/message", json={"content": "How is my fig plant?"})

        assert response.status_code == 201
        body = response.json()
        assert body["role"] == "assistant"
        assert body["content"] == "Your fig plant looks healthy."
        assert body["action_status"] is None


class TestGetConversation:
    async def test_returns_the_conversation_and_messages(self, authenticated_client, harness):
        ac, user = authenticated_client
        org_id = uuid.uuid4()
        harness.grant_role(user, org_id=org_id, role_code="grower", permission_codes=["ai_assistant:use"])
        harness.assistant_orchestrator.run_turn = AsyncMock(return_value=_text_turn_result())
        sent = await ac.post("/api/v1/ai/assistant/message", json={"content": "Hello"})
        conversation_id = sent.json()["conversation_id"]

        response = await ac.get(f"/api/v1/ai/assistant/conversations/{conversation_id}")

        assert response.status_code == 200
        body = response.json()
        assert body["conversation"]["id"] == conversation_id
        assert body["total_messages"] == 2

    async def test_returns_404_for_a_conversation_the_caller_does_not_own(self, authenticated_client, harness):
        ac, user = authenticated_client
        org_id = uuid.uuid4()
        harness.grant_role(user, org_id=org_id, role_code="grower", permission_codes=["ai_assistant:use"])
        harness.assistant_orchestrator.run_turn = AsyncMock(return_value=_text_turn_result())
        sent = await ac.post("/api/v1/ai/assistant/message", json={"content": "Hello"})
        conversation_id = sent.json()["conversation_id"]

        # A second, independent client authenticated as a DIFFERENT user against the same harness/app state --
        # `authenticated_client` only wires up one fixed user, so a genuine cross-user scenario needs its own
        # app instance built the same way that fixture builds its own (see tests/conftest.py's
        # `_apply_common_overrides`/`authenticated_client`).
        other_user = await harness.create_user(email=f"{uuid.uuid4()}@example.com")
        harness.grant_role(other_user, org_id=org_id, role_code="grower", permission_codes=["ai_assistant:use"])
        other_app = create_app(settings=harness.settings)
        _apply_common_overrides(other_app, harness)
        other_app.dependency_overrides[get_current_user] = lambda: other_user
        async with AsyncClient(transport=ASGITransport(app=other_app), base_url="http://testserver") as other_ac:
            response = await other_ac.get(f"/api/v1/ai/assistant/conversations/{conversation_id}")

        assert response.status_code == 404


class TestConfirmAndCancelAction:
    async def test_confirm_requires_confirm_write_permission(self, authenticated_client, harness):
        ac, user = authenticated_client
        org_id = uuid.uuid4()
        branch, plant = await _seed_plant(harness, org_id=org_id)
        harness.grant_role(user, org_id=org_id, role_code="grower", permission_codes=["ai_assistant:use"])
        harness.assistant_orchestrator.run_turn = AsyncMock(return_value=_proposal_turn_result(plant_id=plant.id))
        sent = await ac.post("/api/v1/ai/assistant/message", json={"content": "Log watering for Fig #1."})
        message_id = sent.json()["id"]
        conversation_id = sent.json()["conversation_id"]

        response = await ac.post(
            f"/api/v1/ai/assistant/actions/{message_id}/confirm",
            json={"conversation_id": conversation_id, "confirm": True},
        )

        assert response.status_code == 403

    async def test_confirming_executes_the_underlying_write(self, authenticated_client, harness):
        ac, user = authenticated_client
        org_id = uuid.uuid4()
        branch, plant = await _seed_plant(harness, org_id=org_id)
        harness.grant_role(
            user, org_id=org_id, role_code="branch_manager",
            permission_codes=["ai_assistant:use", "ai_assistant:confirm_write", "watering:write"],
        )
        harness.assistant_orchestrator.run_turn = AsyncMock(return_value=_proposal_turn_result(plant_id=plant.id))
        sent = await ac.post("/api/v1/ai/assistant/message", json={"content": "Log watering for Fig #1."})
        message_id = sent.json()["id"]
        conversation_id = sent.json()["conversation_id"]
        assert sent.json()["action_status"] == "pending_confirmation"

        response = await ac.post(
            f"/api/v1/ai/assistant/actions/{message_id}/confirm",
            json={"conversation_id": conversation_id, "confirm": True},
        )

        assert response.status_code == 200
        assert "recorded" in response.json()["content"].lower()
        watering_rows, total = await harness.watering_logs.list_for_plant(plant.id, offset=0, limit=10)
        assert total == 1
        assert watering_rows[0].volume_ml == 200

    async def test_confirming_twice_returns_conflict(self, authenticated_client, harness):
        ac, user = authenticated_client
        org_id = uuid.uuid4()
        branch, plant = await _seed_plant(harness, org_id=org_id)
        harness.grant_role(
            user, org_id=org_id, role_code="branch_manager",
            permission_codes=["ai_assistant:use", "ai_assistant:confirm_write", "watering:write"],
        )
        harness.assistant_orchestrator.run_turn = AsyncMock(return_value=_proposal_turn_result(plant_id=plant.id))
        sent = await ac.post("/api/v1/ai/assistant/message", json={"content": "Log watering for Fig #1."})
        message_id = sent.json()["id"]
        conversation_id = sent.json()["conversation_id"]
        await ac.post(
            f"/api/v1/ai/assistant/actions/{message_id}/confirm",
            json={"conversation_id": conversation_id, "confirm": True},
        )

        response = await ac.post(
            f"/api/v1/ai/assistant/actions/{message_id}/confirm",
            json={"conversation_id": conversation_id, "confirm": True},
        )

        assert response.status_code == 409

    async def test_cancelling_discards_the_proposal_with_no_watering_recorded(self, authenticated_client, harness):
        ac, user = authenticated_client
        org_id = uuid.uuid4()
        branch, plant = await _seed_plant(harness, org_id=org_id)
        # Only `ai_assistant:use` -- cancelling does NOT require `ai_assistant:confirm_write`.
        harness.grant_role(user, org_id=org_id, role_code="grower", permission_codes=["ai_assistant:use"])
        harness.assistant_orchestrator.run_turn = AsyncMock(return_value=_proposal_turn_result(plant_id=plant.id))
        sent = await ac.post("/api/v1/ai/assistant/message", json={"content": "Log watering for Fig #1."})
        message_id = sent.json()["id"]
        conversation_id = sent.json()["conversation_id"]

        response = await ac.post(
            f"/api/v1/ai/assistant/actions/{message_id}/confirm",
            json={"conversation_id": conversation_id, "confirm": False},
        )

        assert response.status_code == 200
        watering_rows, total = await harness.watering_logs.list_for_plant(plant.id, offset=0, limit=10)
        assert total == 0

    async def test_confirming_a_plain_message_returns_422(self, authenticated_client, harness):
        ac, user = authenticated_client
        org_id = uuid.uuid4()
        harness.grant_role(
            user, org_id=org_id, role_code="branch_manager",
            permission_codes=["ai_assistant:use", "ai_assistant:confirm_write"],
        )
        harness.assistant_orchestrator.run_turn = AsyncMock(return_value=_text_turn_result())
        sent = await ac.post("/api/v1/ai/assistant/message", json={"content": "Just a question."})
        message_id = sent.json()["id"]
        conversation_id = sent.json()["conversation_id"]

        response = await ac.post(
            f"/api/v1/ai/assistant/actions/{message_id}/confirm",
            json={"conversation_id": conversation_id, "confirm": True},
        )

        assert response.status_code == 422
