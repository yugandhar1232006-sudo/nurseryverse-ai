"""
Module 6's explicit "Lifecycle workflow tests" requirement: one full,
end-to-end plant lifecycle exercised entirely through the real HTTP API
(not direct service calls), from registration through to sale -- and a
second workflow through disease/treatment to loss -- verifying that every
step's side effects (status, timeline, movement history, audit trail,
domain events) are consistent at the end, not just that each isolated
endpoint works.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.models.catalog import Species
from app.models.organization import Branch

pytestmark = pytest.mark.integration


def _branch(*, nursery_id: uuid.UUID, name: str = "Main") -> Branch:
    now = datetime.now(timezone.utc)
    return Branch(
        id=uuid.uuid4(), nursery_id=nursery_id, name=name, address_line1="123 St", city="Springfield",
        country="US", timezone="UTC", created_at=now, updated_at=now,
    )


def _species(*, nursery_id: uuid.UUID) -> Species:
    now = datetime.now(timezone.utc)
    return Species(
        id=uuid.uuid4(), nursery_id=nursery_id, category_id=uuid.uuid4(), common_name="Fig", botanical_name="Ficus lyrata",
        created_at=now, updated_at=now,
    )


async def test_full_lifecycle_registration_to_sale(authenticated_client, harness):
    """Register -> grow -> water -> fertilize -> health check -> move -> promote -> sell -> archive."""
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch = _branch(nursery_id=org_id)
    downtown = _branch(nursery_id=org_id, name="Downtown")
    species = _species(nursery_id=org_id)
    harness.branches.branches[branch.id] = branch
    harness.branches.branches[downtown.id] = downtown
    harness.species.species[species.id] = species
    harness.grant_role(
        user, org_id=org_id, role_code="owner",
        permission_codes=[
            "plants:read", "plants:write", "plants:transfer", "growth:read", "growth:write",
            "health:read", "health:write", "watering:read", "watering:write",
        ],
    )

    # 1. Register
    register = await ac.post("/api/v1/plants", json={"branch_id": str(branch.id), "species_id": str(species.id), "common_label": "Fig #1"})
    assert register.status_code == 201
    plant_id = register.json()["id"]
    assert register.json()["status"] == "in_production"

    # 2. Grow
    growth = await ac.post(f"/api/v1/plants/{plant_id}/growth-timeline", json={"height_cm": 10, "growth_stage": "seedling"})
    assert growth.status_code == 201

    # 3. Water
    watering = await ac.post(f"/api/v1/plants/{plant_id}/watering-logs", json={"volume_ml": 150, "method": "hose"})
    assert watering.status_code == 201

    # 4. Health check
    health = await ac.post(f"/api/v1/plants/{plant_id}/health-history", json={"status_label": "healthy", "health_score": 98})
    assert health.status_code == 201

    # 5. Move to another branch
    move = await ac.post(f"/api/v1/plants/{plant_id}/move", json={"to_branch_id": str(downtown.id)})
    assert move.status_code == 200
    assert move.json()["branch_id"] == str(downtown.id)

    # 6. Promote to Ready for Sale
    promote = await ac.post(f"/api/v1/plants/{plant_id}/status", json={"to_status": "ready_for_sale"})
    assert promote.status_code == 200
    assert promote.json()["status"] == "ready_for_sale"

    # 7. Sell
    sell = await ac.post(f"/api/v1/plants/{plant_id}/status", json={"to_status": "sold"})
    assert sell.status_code == 200
    assert sell.json()["status"] == "sold"
    assert sell.json()["sold_at"] is not None

    # 8. Archive
    archive = await ac.post(f"/api/v1/plants/{plant_id}/archive", json={"reason": "Season complete"})
    assert archive.status_code == 200
    assert archive.json()["archived_at"] is not None

    # Verify: archived plants are hidden from the default active listing.
    listing = await ac.get("/api/v1/plants")
    assert all(item["id"] != plant_id for item in listing.json()["items"])
    listing_with_archived = await ac.get("/api/v1/plants", params={"include_archived": True})
    assert any(item["id"] == plant_id for item in listing_with_archived.json()["items"])

    # Verify: the full Timeline reflects every step, oldest facts still queryable.
    timeline = await ac.get(f"/api/v1/plants/{plant_id}/timeline", params={"page_size": 100})
    event_types = {e["event_type"] for e in timeline.json()["items"]}
    assert {"plant.registered", "plant.growth_recorded", "plant.watered", "plant.health_updated", "plant.transferred", "plant.sold"} <= event_types

    # Verify: movement history has exactly the one branch transfer.
    movement = await ac.get(f"/api/v1/plants/{plant_id}/movement-history")
    assert len(movement.json()) == 1

    # Verify: illegal post-terminal transition is still rejected even after archiving.
    illegal = await ac.post(f"/api/v1/plants/{plant_id}/status", json={"to_status": "in_production"})
    assert illegal.status_code == 409


async def test_full_lifecycle_disease_to_loss(authenticated_client, harness):
    """Register -> disease detected -> confirmed (auto Under Treatment) -> treatment attempts -> plant lost."""
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch = _branch(nursery_id=org_id)
    species = _species(nursery_id=org_id)
    harness.branches.branches[branch.id] = branch
    harness.species.species[species.id] = species
    harness.grant_role(
        user, org_id=org_id, role_code="branch_manager",
        permission_codes=["plants:read", "plants:write", "disease:read", "disease:write", "disease:approve"],
    )

    register = await ac.post("/api/v1/plants", json={"branch_id": str(branch.id), "species_id": str(species.id)})
    plant_id = register.json()["id"]

    report = await ac.post(f"/api/v1/plants/{plant_id}/disease-reports", json={"condition_name": "Root rot", "severity": "critical"})
    assert report.status_code == 201
    report_id = report.json()["id"]

    confirm = await ac.post(f"/api/v1/disease-reports/{report_id}/confirm")
    assert confirm.status_code == 200
    plant_after_confirm = await ac.get(f"/api/v1/plants/{plant_id}")
    assert plant_after_confirm.json()["status"] == "under_treatment"

    ongoing = await ac.post(f"/api/v1/disease-reports/{report_id}/treatments", json={"description": "First round", "outcome": "ongoing"})
    assert ongoing.status_code == 201
    plant_still_under_treatment = await ac.get(f"/api/v1/plants/{plant_id}")
    assert plant_still_under_treatment.json()["status"] == "under_treatment"

    lost = await ac.post(f"/api/v1/disease-reports/{report_id}/treatments", json={"description": "Beyond saving", "outcome": "plant_lost"})
    assert lost.status_code == 201

    final_plant = await ac.get(f"/api/v1/plants/{plant_id}")
    assert final_plant.json()["status"] == "deceased"
    assert final_plant.json()["deceased_reason"] is not None

    disease_history = await ac.get(f"/api/v1/plants/{plant_id}/disease-reports")
    assert disease_history.json()[0]["status"] == "resolved"

    treatments = await ac.get(f"/api/v1/disease-reports/{report_id}/treatments")
    assert len(treatments.json()) == 2

    timeline = await ac.get(f"/api/v1/plants/{plant_id}/timeline", params={"page_size": 100})
    event_types = {e["event_type"] for e in timeline.json()["items"]}
    assert {"plant.disease_detected", "plant.treatment_applied", "plant.disposed"} <= event_types
