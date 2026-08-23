"""
Unit tests for `AssistantToolRegistry` (Module 10 AI Assistant). Per the
class's own docstring, the two things that matter most to verify: (1)
every tool re-runs the SAME `AuthorizationService.authorize()` check the
equivalent native route would -- a user without the underlying permission
gets denied through the Assistant exactly as they would clicking a page,
and (2) write tools (`propose_*`) never execute a mutation themselves --
only `execute_confirmed_action` (called later, post human-confirmation)
does, via the same real service methods a native page uses.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.core.exceptions import NotFoundError
from app.models.catalog import Species
from app.models.organization import Branch
from app.services.authorization_service import RequestContext

pytestmark = pytest.mark.unit

_CTX = RequestContext(request_id="req-assistant-1", ip_address="203.0.113.9")


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


async def _register_plant(harness, *, org_id: uuid.UUID):
    branch = _branch(nursery_id=org_id)
    species = _species(nursery_id=org_id)
    harness.branches.branches[branch.id] = branch
    harness.species.species[species.id] = species
    plant = await harness.plant_service.register_plant(
        nursery_id=org_id, branch_id=branch.id, species_id=species.id, actor_user_id=uuid.uuid4()
    )
    return branch, plant


async def _authorized_user(harness, *, org_id: uuid.UUID, permission_codes: list[str]):
    user = await harness.create_user(email=f"{uuid.uuid4()}@example.com")
    harness.grant_role(user, org_id=org_id, role_code="grower", permission_codes=permission_codes)
    return user


class TestGetPlantSummary:
    async def test_returns_plant_summary_when_authorized(self, harness):
        org_id = uuid.uuid4()
        _, plant = await _register_plant(harness, org_id=org_id)
        user = await _authorized_user(harness, org_id=org_id, permission_codes=["plants:read"])
        registry = harness.build_assistant_tool_registry(
            user=user, org_id=org_id, authz=harness.authorization_service, request_context=_CTX
        )

        result = await registry.invoke("get_plant_summary", {"plant_id": str(plant.id)})

        assert result["plant_id"] == str(plant.id)
        assert "error" not in result

    async def test_returns_error_for_unknown_plant(self, harness):
        org_id = uuid.uuid4()
        user = await _authorized_user(harness, org_id=org_id, permission_codes=["plants:read"])
        registry = harness.build_assistant_tool_registry(
            user=user, org_id=org_id, authz=harness.authorization_service, request_context=_CTX
        )

        result = await registry.invoke("get_plant_summary", {"plant_id": str(uuid.uuid4())})

        assert result == {"error": "Plant not found."}

    async def test_denies_when_user_lacks_plants_read_permission(self, harness):
        org_id = uuid.uuid4()
        _, plant = await _register_plant(harness, org_id=org_id)
        user = await _authorized_user(harness, org_id=org_id, permission_codes=["inventory:read"])  # wrong permission
        registry = harness.build_assistant_tool_registry(
            user=user, org_id=org_id, authz=harness.authorization_service, request_context=_CTX
        )

        result = await registry.invoke("get_plant_summary", {"plant_id": str(plant.id)})

        assert result == {"error": "You do not have permission to view this plant."}

    async def test_denies_a_cross_tenant_plant(self, harness):
        owner_org = uuid.uuid4()
        other_org = uuid.uuid4()
        _, plant = await _register_plant(harness, org_id=owner_org)
        # Authorized for a DIFFERENT org -- must not see the other tenant's plant.
        user = await _authorized_user(harness, org_id=other_org, permission_codes=["plants:read"])
        registry = harness.build_assistant_tool_registry(
            user=user, org_id=other_org, authz=harness.authorization_service, request_context=_CTX
        )

        result = await registry.invoke("get_plant_summary", {"plant_id": str(plant.id)})

        assert result == {"error": "You do not have permission to view this plant."}


class TestListPlants:
    async def test_returns_plants_when_authorized(self, harness):
        org_id = uuid.uuid4()
        await _register_plant(harness, org_id=org_id)
        user = await _authorized_user(harness, org_id=org_id, permission_codes=["plants:read"])
        registry = harness.build_assistant_tool_registry(
            user=user, org_id=org_id, authz=harness.authorization_service, request_context=_CTX
        )

        result = await registry.invoke("list_plants", {})

        assert "plants" in result
        assert "total" in result
        assert result["total"] >= 1
        assert "error" not in result

    async def test_denies_when_user_lacks_plants_read_permission(self, harness):
        org_id = uuid.uuid4()
        user = await _authorized_user(harness, org_id=org_id, permission_codes=["inventory:read"])
        registry = harness.build_assistant_tool_registry(
            user=user, org_id=org_id, authz=harness.authorization_service, request_context=_CTX
        )

        result = await registry.invoke("list_plants", {})

        assert result == {"error": "You do not have permission to view plants."}

    async def test_returns_error_with_no_org_context(self, harness):
        user = await harness.create_user(email=f"{uuid.uuid4()}@example.com")
        registry = harness.build_assistant_tool_registry(
            user=user, org_id=None, authz=harness.authorization_service, request_context=_CTX
        )

        result = await registry.invoke("list_plants", {})

        assert result == {"error": "No organization context."}

    async def test_filters_by_status(self, harness):
        org_id = uuid.uuid4()
        user = await _authorized_user(harness, org_id=org_id, permission_codes=["plants:read"])
        registry = harness.build_assistant_tool_registry(
            user=user, org_id=org_id, authz=harness.authorization_service, request_context=_CTX
        )

        result = await registry.invoke("list_plants", {"status": "in_production"})

        assert "plants" in result
        assert "error" not in result


class TestGetInventoryStatus:
    async def test_returns_error_with_no_org_context(self, harness):
        user = await harness.create_user(email=f"{uuid.uuid4()}@example.com")
        registry = harness.build_assistant_tool_registry(
            user=user, org_id=None, authz=harness.authorization_service, request_context=_CTX
        )

        result = await registry.invoke("get_inventory_status", {"branch_id": str(uuid.uuid4())})

        assert result == {"error": "No organization context."}

    async def test_returns_summary_when_authorized(self, harness):
        org_id = uuid.uuid4()
        branch, _ = await _register_plant(harness, org_id=org_id)
        user = await _authorized_user(harness, org_id=org_id, permission_codes=["inventory:read"])
        registry = harness.build_assistant_tool_registry(
            user=user, org_id=org_id, authz=harness.authorization_service, request_context=_CTX
        )

        result = await registry.invoke("get_inventory_status", {"branch_id": str(branch.id)})

        assert "error" not in result

    async def test_denies_without_inventory_read_permission(self, harness):
        org_id = uuid.uuid4()
        branch, _ = await _register_plant(harness, org_id=org_id)
        user = await _authorized_user(harness, org_id=org_id, permission_codes=["plants:read"])
        registry = harness.build_assistant_tool_registry(
            user=user, org_id=org_id, authz=harness.authorization_service, request_context=_CTX
        )

        result = await registry.invoke("get_inventory_status", {"branch_id": str(branch.id)})

        assert result == {"error": "You do not have permission to view inventory for this branch."}


class TestGetSalesSummary:
    async def test_returns_error_with_no_org_context(self, harness):
        user = await harness.create_user(email=f"{uuid.uuid4()}@example.com")
        registry = harness.build_assistant_tool_registry(
            user=user, org_id=None, authz=harness.authorization_service, request_context=_CTX
        )

        result = await registry.invoke("get_sales_summary", {})

        assert result == {"error": "No organization context."}

    async def test_returns_summary_when_authorized(self, harness):
        org_id = uuid.uuid4()
        user = await _authorized_user(harness, org_id=org_id, permission_codes=["sales:read"])
        registry = harness.build_assistant_tool_registry(
            user=user, org_id=org_id, authz=harness.authorization_service, request_context=_CTX
        )

        result = await registry.invoke("get_sales_summary", {})

        assert "error" not in result

    async def test_denies_without_sales_read_permission(self, harness):
        org_id = uuid.uuid4()
        user = await _authorized_user(harness, org_id=org_id, permission_codes=["plants:read"])
        registry = harness.build_assistant_tool_registry(
            user=user, org_id=org_id, authz=harness.authorization_service, request_context=_CTX
        )

        result = await registry.invoke("get_sales_summary", {})

        assert result == {"error": "You do not have permission to view sales data."}


class TestGetAIPredictions:
    async def test_returns_empty_predictions_list_when_none_exist(self, harness):
        org_id = uuid.uuid4()
        _, plant = await _register_plant(harness, org_id=org_id)
        user = await _authorized_user(harness, org_id=org_id, permission_codes=["ai_predictions:read"])
        registry = harness.build_assistant_tool_registry(
            user=user, org_id=org_id, authz=harness.authorization_service, request_context=_CTX
        )

        result = await registry.invoke("get_ai_predictions", {"plant_id": str(plant.id)})

        assert result == {"total": 0, "predictions": []}

    async def test_denies_without_ai_predictions_read_permission(self, harness):
        org_id = uuid.uuid4()
        _, plant = await _register_plant(harness, org_id=org_id)
        user = await _authorized_user(harness, org_id=org_id, permission_codes=["plants:read"])
        registry = harness.build_assistant_tool_registry(
            user=user, org_id=org_id, authz=harness.authorization_service, request_context=_CTX
        )

        result = await registry.invoke("get_ai_predictions", {"plant_id": str(plant.id)})

        assert result == {"error": "You do not have permission to view AI predictions for this plant."}


class TestProposeWriteTools:
    """FR-9.3's confirmation gate: propose_* tools NEVER execute a write themselves."""

    async def test_propose_watering_log_returns_a_proposal_without_recording_anything(self, harness):
        org_id = uuid.uuid4()
        _, plant = await _register_plant(harness, org_id=org_id)
        user = await _authorized_user(harness, org_id=org_id, permission_codes=["watering:write"])
        registry = harness.build_assistant_tool_registry(
            user=user, org_id=org_id, authz=harness.authorization_service, request_context=_CTX
        )

        result = await registry.invoke("propose_watering_log", {"plant_id": str(plant.id), "volume_ml": 250})

        assert result["requires_confirmation"] is True
        assert result["tool_name"] == "propose_watering_log"
        assert result["tool_arguments"]["volume_ml"] == 250
        watering_rows, _ = await harness.watering_logs.list_for_plant(plant.id, offset=0, limit=10)
        assert watering_rows == []

    async def test_propose_watering_log_denies_without_watering_write_permission(self, harness):
        org_id = uuid.uuid4()
        _, plant = await _register_plant(harness, org_id=org_id)
        user = await _authorized_user(harness, org_id=org_id, permission_codes=["plants:read"])
        registry = harness.build_assistant_tool_registry(
            user=user, org_id=org_id, authz=harness.authorization_service, request_context=_CTX
        )

        result = await registry.invoke("propose_watering_log", {"plant_id": str(plant.id)})

        assert result == {"error": "You do not have permission to record watering for this plant."}

    async def test_propose_health_observation_returns_a_proposal_without_recording_anything(self, harness):
        org_id = uuid.uuid4()
        _, plant = await _register_plant(harness, org_id=org_id)
        user = await _authorized_user(harness, org_id=org_id, permission_codes=["health:write"])
        registry = harness.build_assistant_tool_registry(
            user=user, org_id=org_id, authz=harness.authorization_service, request_context=_CTX
        )

        result = await registry.invoke(
            "propose_health_observation", {"plant_id": str(plant.id), "status_label": "stressed"}
        )

        assert result["requires_confirmation"] is True
        assert result["tool_arguments"]["status_label"] == "stressed"
        health_rows, _ = await harness.health_history.list_for_plant(plant.id, offset=0, limit=10)
        assert health_rows == []

    async def test_propose_tools_return_error_for_unknown_plant(self, harness):
        org_id = uuid.uuid4()
        user = await _authorized_user(harness, org_id=org_id, permission_codes=["watering:write"])
        registry = harness.build_assistant_tool_registry(
            user=user, org_id=org_id, authz=harness.authorization_service, request_context=_CTX
        )

        result = await registry.invoke("propose_watering_log", {"plant_id": str(uuid.uuid4())})

        assert result == {"error": "Plant not found."}


class TestExecuteConfirmedAction:
    async def test_execute_confirmed_watering_actually_records_it(self, harness):
        org_id = uuid.uuid4()
        _, plant = await _register_plant(harness, org_id=org_id)
        user = await _authorized_user(harness, org_id=org_id, permission_codes=["watering:write"])
        registry = harness.build_assistant_tool_registry(
            user=user, org_id=org_id, authz=harness.authorization_service, request_context=_CTX
        )

        summary = await registry.execute_confirmed_action(
            tool_name="propose_watering_log", tool_arguments={"plant_id": str(plant.id), "volume_ml": 300}
        )

        assert "recorded" in summary.lower()
        watering_rows, total = await harness.watering_logs.list_for_plant(plant.id, offset=0, limit=10)
        assert total == 1
        assert watering_rows[0].volume_ml == 300

    async def test_execute_confirmed_health_observation_actually_records_it(self, harness):
        org_id = uuid.uuid4()
        _, plant = await _register_plant(harness, org_id=org_id)
        user = await _authorized_user(harness, org_id=org_id, permission_codes=["health:write"])
        registry = harness.build_assistant_tool_registry(
            user=user, org_id=org_id, authz=harness.authorization_service, request_context=_CTX
        )

        summary = await registry.execute_confirmed_action(
            tool_name="propose_health_observation",
            tool_arguments={"plant_id": str(plant.id), "status_label": "recovering"},
        )

        assert "recorded" in summary.lower()
        health_rows, total = await harness.health_history.list_for_plant(plant.id, offset=0, limit=10)
        assert total == 1
        assert health_rows[0].status_label == "recovering"

    async def test_execute_confirmed_action_raises_for_an_unknown_tool(self, harness):
        org_id = uuid.uuid4()
        user = await harness.create_user(email=f"{uuid.uuid4()}@example.com")
        registry = harness.build_assistant_tool_registry(
            user=user, org_id=org_id, authz=harness.authorization_service, request_context=_CTX
        )

        with pytest.raises(NotFoundError):
            await registry.execute_confirmed_action(tool_name="not_a_real_tool", tool_arguments={})


class TestToolDefinitionsAndDispatch:
    async def test_tool_definitions_cover_every_registered_tool(self, harness):
        org_id = uuid.uuid4()
        user = await harness.create_user(email=f"{uuid.uuid4()}@example.com")
        registry = harness.build_assistant_tool_registry(
            user=user, org_id=org_id, authz=harness.authorization_service, request_context=_CTX
        )

        names = {d["name"] for d in registry.tool_definitions()}

        assert names == {
            "list_plants", "get_plant_summary", "get_inventory_status", "get_sales_summary", "get_ai_predictions",
            "propose_watering_log", "propose_health_observation",
        }

    async def test_invoke_returns_error_for_an_unregistered_tool_name(self, harness):
        org_id = uuid.uuid4()
        user = await harness.create_user(email=f"{uuid.uuid4()}@example.com")
        registry = harness.build_assistant_tool_registry(
            user=user, org_id=org_id, authz=harness.authorization_service, request_context=_CTX
        )

        result = await registry.invoke("delete_everything", {})

        assert result == {"error": "Unknown tool 'delete_everything'."}
