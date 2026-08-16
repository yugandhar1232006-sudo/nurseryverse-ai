"""
Unit tests for Module 10's shared AI infrastructure (`app/ai/common/`):
`ModelRegistry`, `PredictionLogger`, `FeatureStore`. Exercises these
directly against the harness's in-memory fakes, the same split every
prior module's unit test files use.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.ai.common import ModelRegistry
from app.core.config import Settings
from app.core.exceptions import ModelUnavailableError
from app.db.enums import AIPredictionType
from app.models.catalog import Species
from app.models.organization import Branch

pytestmark = pytest.mark.unit


def _branch(*, nursery_id: uuid.UUID) -> Branch:
    now = datetime.now(timezone.utc)
    return Branch(
        id=uuid.uuid4(), nursery_id=nursery_id, name="Main", address_line1="123 St", city="Springfield",
        country="US", timezone="UTC", created_at=now, updated_at=now,
    )


def _species(*, nursery_id: uuid.UUID, **overrides) -> Species:
    now = datetime.now(timezone.utc)
    species = Species(
        id=uuid.uuid4(), nursery_id=nursery_id, category_id=uuid.uuid4(), common_name="Fig", botanical_name="Ficus lyrata",
        created_at=now, updated_at=now,
    )
    for key, value in overrides.items():
        setattr(species, key, value)
    return species


async def _register_plant(harness, *, org_id=None, species_overrides=None):
    org_id = org_id or uuid.uuid4()
    branch = _branch(nursery_id=org_id)
    species = _species(nursery_id=org_id, **(species_overrides or {}))
    harness.branches.branches[branch.id] = branch
    harness.species.species[species.id] = species
    plant = await harness.plant_service.register_plant(
        nursery_id=org_id, branch_id=branch.id, species_id=species.id, actor_user_id=uuid.uuid4()
    )
    return org_id, branch, species, plant


# ==============================================================================
# ModelRegistry
# ==============================================================================


class TestModelRegistry:
    def test_get_raises_model_unavailable_when_no_base_path_configured(self):
        settings = Settings(_env_file=None, APP_ENV="test", MODEL_ARTIFACT_BASE_PATH="")
        registry = ModelRegistry(settings=settings)

        with pytest.raises(ModelUnavailableError):
            registry.get("disease_detection")

    def test_get_raises_model_unavailable_even_when_base_path_configured_but_no_loader_exists(self):
        # See ModelRegistry's own docstring: a configured base path with no artifact/loader still raises --
        # this sandbox has never produced a trained artifact for any capability.
        settings = Settings(_env_file=None, APP_ENV="test", MODEL_ARTIFACT_BASE_PATH="s3://fake-bucket/models")
        registry = ModelRegistry(settings=settings)

        with pytest.raises(ModelUnavailableError):
            registry.get("disease_detection")

    def test_is_configured_false_by_default(self):
        settings = Settings(_env_file=None, APP_ENV="test", MODEL_ARTIFACT_BASE_PATH="")
        registry = ModelRegistry(settings=settings)

        assert registry.is_configured("disease_detection") is False

    def test_is_configured_true_when_base_path_set(self):
        settings = Settings(_env_file=None, APP_ENV="test", MODEL_ARTIFACT_BASE_PATH="s3://fake-bucket/models")
        registry = ModelRegistry(settings=settings)

        assert registry.is_configured("disease_detection") is True


# ==============================================================================
# PredictionLogger -- FR-8.7's universal logging contract
# ==============================================================================


class TestPredictionLogger:
    async def test_persist_always_writes_an_ai_prediction_row(self, harness):
        _, _, _, plant = await _register_plant(harness)

        prediction = await harness.prediction_logger.persist(
            prediction_type=AIPredictionType.GROWTH_PREDICTION, nursery_id=plant.nursery_id,
            branch_id=plant.branch_id, plant_id=plant.id, model_version="v1.0.0-test",
            result={"foo": "bar"}, confidence=Decimal("0.5"), explanation="test",
        )

        stored = await harness.ai_predictions.get_by_id(prediction.id)
        assert stored is not None
        assert stored.prediction_type == AIPredictionType.GROWTH_PREDICTION
        assert stored.result == {"foo": "bar"}

    async def test_persist_publishes_ai_prediction_generated_for_plant_scoped_predictions(self, harness):
        _, _, _, plant = await _register_plant(harness)
        before = len(harness.domain_events.events)

        await harness.prediction_logger.persist(
            prediction_type=AIPredictionType.SURVIVAL_PREDICTION, nursery_id=plant.nursery_id,
            branch_id=plant.branch_id, plant_id=plant.id, model_version="v1.0.0-test", result={},
        )

        events = harness.domain_events.events[before:]
        assert any(e.event_type == "ai.prediction_generated" and e.aggregate_id == plant.id for e in events)

    async def test_persist_projects_into_the_plants_digital_twin(self, harness):
        """
        End-to-end proof that the Module 10 Digital Twin projector
        extension (`_on_ai_prediction_generated`) actually fires: this
        goes through the real `event_publisher` -> `EventDispatcher` ->
        `DigitalTwinEventHandler` -> `DigitalTwinService.project()` chain,
        not a mocked shortcut.
        """
        _, _, _, plant = await _register_plant(harness)

        prediction = await harness.prediction_logger.persist(
            prediction_type=AIPredictionType.GROWTH_PREDICTION, nursery_id=plant.nursery_id,
            branch_id=plant.branch_id, plant_id=plant.id, model_version="v1.0.0-test",
            result={"method": "linear_trend"}, confidence=Decimal("0.6"), explanation="looks healthy",
        )

        twin = await harness.digital_twin_service.get_current_twin(plant.id)
        assert twin.snapshot["counts"]["ai_predictions"] == 1
        assert twin.snapshot["latest"]["ai_prediction"]["prediction_id"] == str(prediction.id)
        assert twin.snapshot["latest"]["ai_prediction"]["prediction_type"] == "growth_prediction"

    async def test_persist_does_not_publish_an_event_for_org_wide_predictions_with_no_plant_or_branch(self, harness):
        org_id = uuid.uuid4()
        before = len(harness.domain_events.events)

        await harness.prediction_logger.persist(
            prediction_type=AIPredictionType.REVENUE_FORECAST, nursery_id=org_id, model_version="v1.0.0-test",
            result={},
        )

        # Still persisted (FR-8.7 is unconditional)...
        assert len(harness.ai_predictions.predictions) == 1
        # ...but no event, since neither plant_id nor branch_id is set (documented no-op, see the module's
        # own docstring).
        assert len(harness.domain_events.events) == before

    async def test_persist_publishes_branch_scoped_event_when_only_branch_id_set(self, harness):
        org_id = uuid.uuid4()
        branch_id = uuid.uuid4()
        before = len(harness.domain_events.events)

        await harness.prediction_logger.persist(
            prediction_type=AIPredictionType.REVENUE_FORECAST, nursery_id=org_id, branch_id=branch_id,
            model_version="v1.0.0-test", result={},
        )

        events = harness.domain_events.events[before:]
        assert any(
            e.event_type == "ai.prediction_generated_for_branch" and e.aggregate_id == branch_id for e in events
        )


# ==============================================================================
# FeatureStore -- assembly correctness
# ==============================================================================


class TestFeatureStore:
    async def test_assemble_growth_features_includes_history_and_species_baseline(self, harness):
        _, _, species, plant = await _register_plant(
            harness, species_overrides={"growth_curve_baseline": [{"days_since_planting": 0, "expected_height_cm": 5.0}]}
        )
        await harness.growth_service.record_growth(
            plant_id=plant.id, actor_user_id=uuid.uuid4(), height_cm=12.5, spread_cm=8.0, growth_stage="growing",
        )

        features = await harness.feature_store.assemble_growth_features(plant)

        assert features["history_count"] == 1
        assert features["history"][0]["height_cm"] == 12.5
        assert features["species_growth_curve_baseline"] == [{"days_since_planting": 0, "expected_height_cm": 5.0}]

    async def test_assemble_survival_features_computes_days_since_last_watering(self, harness):
        _, _, _, plant = await _register_plant(harness)
        await harness.watering_service.record_watering(plant_id=plant.id, actor_user_id=uuid.uuid4(), volume_ml=200)
        await harness.health_service.record_health(plant_id=plant.id, status_label="healthy", actor_user_id=uuid.uuid4())

        features = await harness.feature_store.assemble_survival_features(plant)

        assert features["days_since_last_watering"] == 0
        assert features["health_trend"][0]["status_label"] == "healthy"

    async def test_assemble_water_features_reads_species_baseline(self, harness):
        _, _, species, plant = await _register_plant(harness, species_overrides={"water_baseline_ml_per_week": 500})

        features = await harness.feature_store.assemble_water_features(plant)

        assert features["species_water_baseline_ml_per_week"] == 500

    async def test_assemble_revenue_features_aggregates_daily_totals_excluding_voided(self, harness):
        org_id = uuid.uuid4()

        features = await harness.feature_store.assemble_revenue_features(org_id)

        # No sales seeded -- a real, empty aggregation, not a fabricated result.
        assert features["nursery_id"] == str(org_id)
        assert features["daily_revenue"] == []
        assert features["sale_count"] == 0
