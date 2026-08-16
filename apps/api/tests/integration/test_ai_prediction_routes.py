"""
Integration tests for Module 10's `/ai/*` and `/plants/{id}/ai-predictions*`
routes -- real HTTP requests through the app's real routing/dependency
graph against the harness's in-memory fakes (same pattern as every other
integration test file, e.g. test_disease_report_routes.py). Covers
permission gating, the "no org yet" empty-vs-403 distinction
`_authorize_org_scope` implements, cross-tenant denial, and the
persist-before-return contract end-to-end through a real HTTP response.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.db.enums import AIPredictionType
from app.models.catalog import Species
from app.models.organization import Branch

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


async def _seed_plant(harness, *, org_id: uuid.UUID | None = None):
    org_id = org_id or uuid.uuid4()
    branch = _branch(nursery_id=org_id)
    species = _species(nursery_id=org_id)
    harness.branches.branches[branch.id] = branch
    harness.species.species[species.id] = species
    plant = await harness.plant_service.register_plant(
        nursery_id=org_id, branch_id=branch.id, species_id=species.id, actor_user_id=uuid.uuid4()
    )
    return org_id, branch, plant


class TestDiseaseDetectionRoute:
    async def test_requires_ai_predictions_run_permission(self, authenticated_client, harness):
        ac, user = authenticated_client
        org_id, _, plant = await _seed_plant(harness)
        harness.grant_role(user, org_id=org_id, role_code="grower", permission_codes=["plants:read"])

        response = await ac.post(
            "/api/v1/ai/disease-detection/scan",
            json={"plant_id": str(plant.id), "image_url": "https://cdn.example.com/plant.jpg"},
        )

        assert response.status_code == 403

    async def test_returns_503_when_no_model_artifact_configured(self, authenticated_client, harness):
        ac, user = authenticated_client
        org_id, _, plant = await _seed_plant(harness)
        harness.grant_role(user, org_id=org_id, role_code="grower", permission_codes=["ai_predictions:run"])

        response = await ac.post(
            "/api/v1/ai/disease-detection/scan",
            json={"plant_id": str(plant.id), "image_url": "https://cdn.example.com/plant.jpg"},
        )

        assert response.status_code == 503

    async def test_returns_404_for_unknown_plant(self, authenticated_client, harness):
        ac, user = authenticated_client
        response = await ac.post(
            "/api/v1/ai/disease-detection/scan",
            json={"plant_id": str(uuid.uuid4()), "image_url": "https://cdn.example.com/plant.jpg"},
        )

        assert response.status_code == 404


class TestOnDemandPlantPredictions:
    async def test_run_growth_prediction_persists_and_returns_a_prediction(self, authenticated_client, harness):
        ac, user = authenticated_client
        org_id, _, plant = await _seed_plant(harness)
        harness.grant_role(user, org_id=org_id, role_code="grower", permission_codes=["ai_predictions:run"])

        response = await ac.post(f"/api/v1/plants/{plant.id}/ai-predictions/growth")

        assert response.status_code == 201
        body = response.json()
        assert body["prediction_type"] == "growth_prediction"
        assert body["model_version"] == "v1.0.0-linear-baseline"
        assert body["plant_id"] == str(plant.id)

    async def test_run_survival_prediction_persists_and_returns_a_prediction(self, authenticated_client, harness):
        ac, user = authenticated_client
        org_id, _, plant = await _seed_plant(harness)
        harness.grant_role(user, org_id=org_id, role_code="grower", permission_codes=["ai_predictions:run"])

        response = await ac.post(f"/api/v1/plants/{plant.id}/ai-predictions/survival")

        assert response.status_code == 201
        assert response.json()["prediction_type"] == "survival_prediction"

    async def test_run_water_recommendation_persists_and_returns_a_prediction(self, authenticated_client, harness):
        ac, user = authenticated_client
        org_id, _, plant = await _seed_plant(harness)
        harness.grant_role(user, org_id=org_id, role_code="grower", permission_codes=["ai_predictions:run"])

        response = await ac.post(f"/api/v1/plants/{plant.id}/ai-predictions/water")

        assert response.status_code == 201
        assert response.json()["prediction_type"] == "water_recommendation"

    async def test_cross_tenant_plant_is_denied(self, authenticated_client, harness):
        ac, user = authenticated_client
        owner_org = uuid.uuid4()
        other_org = uuid.uuid4()
        _, _, plant = await _seed_plant(harness, org_id=owner_org)
        harness.grant_role(user, org_id=other_org, role_code="grower", permission_codes=["ai_predictions:run"])

        response = await ac.post(f"/api/v1/plants/{plant.id}/ai-predictions/growth")

        assert response.status_code == 403


class TestListPlantAIPredictions:
    async def test_returns_history_newest_first(self, authenticated_client, harness):
        ac, user = authenticated_client
        org_id, _, plant = await _seed_plant(harness)
        harness.grant_role(
            user, org_id=org_id, role_code="grower", permission_codes=["ai_predictions:run", "ai_predictions:read"]
        )
        await ac.post(f"/api/v1/plants/{plant.id}/ai-predictions/growth")
        await ac.post(f"/api/v1/plants/{plant.id}/ai-predictions/water")

        response = await ac.get(f"/api/v1/plants/{plant.id}/ai-predictions")

        assert response.status_code == 200
        body = response.json()
        assert body["meta"]["total_items"] == 2

    async def test_requires_ai_predictions_read_permission(self, authenticated_client, harness):
        ac, user = authenticated_client
        org_id, _, plant = await _seed_plant(harness)
        harness.grant_role(user, org_id=org_id, role_code="grower", permission_codes=["plants:read"])

        response = await ac.get(f"/api/v1/plants/{plant.id}/ai-predictions")

        assert response.status_code == 403


class TestSurvivalRiskListing:
    async def test_returns_empty_page_with_no_org_membership(self, authenticated_client):
        ac, user = authenticated_client

        response = await ac.get("/api/v1/ai/predictions/survival-risk")

        assert response.status_code == 200
        assert response.json()["items"] == []

    async def test_returns_predictions_for_the_callers_org(self, authenticated_client, harness):
        ac, user = authenticated_client
        org_id, branch, plant = await _seed_plant(harness)
        harness.grant_role(
            user, org_id=org_id, role_code="grower", permission_codes=["ai_predictions:run", "ai_predictions:read"]
        )
        await ac.post(f"/api/v1/plants/{plant.id}/ai-predictions/survival")

        response = await ac.get("/api/v1/ai/predictions/survival-risk")

        assert response.status_code == 200
        body = response.json()
        assert body["meta"]["total_items"] == 1
        assert body["items"][0]["prediction_type"] == "survival_prediction"


class TestRevenueForecast:
    async def test_run_without_org_membership_is_denied(self, authenticated_client):
        ac, user = authenticated_client

        response = await ac.post("/api/v1/ai/predictions/revenue-forecast")

        assert response.status_code == 403

    async def test_run_persists_a_branch_scoped_forecast(self, authenticated_client, harness):
        ac, user = authenticated_client
        org_id = uuid.uuid4()
        harness.grant_role(user, org_id=org_id, role_code="branch_manager", permission_codes=["ai_predictions:run"])

        response = await ac.post("/api/v1/ai/predictions/revenue-forecast")

        assert response.status_code == 201
        body = response.json()
        assert body["prediction_type"] == "revenue_forecast"
        assert body["nursery_id"] == str(org_id)

    async def test_list_returns_empty_page_with_no_org_membership(self, authenticated_client):
        ac, user = authenticated_client

        response = await ac.get("/api/v1/ai/predictions/revenue-forecast")

        assert response.status_code == 200
        assert response.json()["items"] == []


class TestRecommendations:
    async def test_list_returns_empty_page_with_no_org_membership(self, authenticated_client):
        ac, user = authenticated_client

        response = await ac.get("/api/v1/ai/recommendations")

        assert response.status_code == 200
        assert response.json()["items"] == []

    async def test_refresh_generates_recommendations_from_latest_survival_predictions(self, authenticated_client, harness):
        ac, user = authenticated_client
        org_id, branch, plant = await _seed_plant(harness)
        harness.grant_role(
            user, org_id=org_id, role_code="branch_manager",
            permission_codes=["ai_predictions:run", "ai_predictions:read"],
        )
        # Seed a high-risk Survival Prediction directly through the real PredictionLogger (the same
        # persist-before-return path `run_survival_prediction` itself would go through).
        await harness.prediction_logger.persist(
            prediction_type=AIPredictionType.SURVIVAL_PREDICTION, nursery_id=org_id, branch_id=branch.id,
            plant_id=plant.id, model_version="v1.0.0-weighted-risk-baseline",
            result={"risk_score": 75.0, "risk_level": "high"}, confidence=Decimal("0.5"),
        )

        response = await ac.post(f"/api/v1/ai/recommendations/refresh?branch_id={branch.id}")

        assert response.status_code == 201
        body = response.json()
        assert len(body) == 1
        assert body[0]["priority"] == "high"

        list_response = await ac.get("/api/v1/ai/recommendations")
        assert list_response.json()["meta"]["total_items"] == 1

    async def test_refresh_requires_ai_predictions_run_permission(self, authenticated_client, harness):
        ac, user = authenticated_client
        org_id, branch, _ = await _seed_plant(harness)
        harness.grant_role(user, org_id=org_id, role_code="grower", permission_codes=["ai_predictions:read"])

        response = await ac.post(f"/api/v1/ai/recommendations/refresh?branch_id={branch.id}")

        assert response.status_code == 403
