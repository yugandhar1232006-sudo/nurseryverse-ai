"""
Unit tests for Module 10's six prediction inference modules
(`app/ai/disease_detection`, `growth_prediction`, `survival_prediction`,
`water_recommendation`, `revenue_forecast`; `recommendation_engine` has
its own dedicated test file since it composes over other predictions
rather than implementing `InferenceBase`).

Each module's `preprocess`/`predict`/`postprocess` are pure functions of
their input dict -- exercised directly here, no repository/harness
needed. One `run()` end-to-end test per module (via the harness's real
`PredictionLogger`) proves the `InferenceBase.run()` persist-before-
return contract (FR-8.7) actually fires for that module's real output
shape, not just for the generic fixtures in `test_ai_common.py`.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.ai.disease_detection.inference import DiseaseDetectionInference
from app.ai.growth_prediction.inference import GrowthPredictionInference
from app.ai.revenue_forecast.inference import RevenueForecastInference
from app.ai.survival_prediction.inference import SurvivalPredictionInference
from app.ai.water_recommendation.inference import WaterRecommendationInference
from app.core.exceptions import ModelUnavailableError, ValidationError

pytestmark = pytest.mark.unit


# ==============================================================================
# Disease Detection -- no non-ML fallback; always ModelUnavailableError
# ==============================================================================


class TestDiseaseDetectionInference:
    async def test_preprocess_requires_image_url(self, harness):
        inference = DiseaseDetectionInference(
            prediction_logger=harness.prediction_logger, model_registry=harness.model_registry
        )
        with pytest.raises(ValidationError):
            await inference.preprocess({})

    async def test_predict_raises_model_unavailable_no_trained_artifact(self, harness):
        inference = DiseaseDetectionInference(
            prediction_logger=harness.prediction_logger, model_registry=harness.model_registry
        )
        preprocessed = await inference.preprocess({"image_url": "https://cdn.example.com/plant.jpg"})

        with pytest.raises(ModelUnavailableError):
            await inference.predict(preprocessed)

    async def test_run_propagates_model_unavailable_without_persisting(self, harness):
        """The graceful-degradation path: run() never reaches persist() when predict() raises."""
        inference = DiseaseDetectionInference(
            prediction_logger=harness.prediction_logger, model_registry=harness.model_registry
        )
        nursery_id = uuid.uuid4()
        before = len(harness.ai_predictions.predictions)

        with pytest.raises(ModelUnavailableError):
            await inference.run(nursery_id=nursery_id, features={"image_url": "https://cdn.example.com/plant.jpg"})

        assert len(harness.ai_predictions.predictions) == before


# ==============================================================================
# Growth Prediction -- linear trend / species baseline / insufficient data
# ==============================================================================


class TestGrowthPredictionInference:
    async def test_predict_uses_linear_trend_with_two_or_more_points(self):
        inference = GrowthPredictionInference(prediction_logger=None)  # type: ignore[arg-type]
        preprocessed = {
            "history": [
                {"height_cm": 10.0, "days_since_planting": 0},
                {"height_cm": 20.0, "days_since_planting": 10},
            ],
            "species_growth_curve_baseline": [],
        }

        model_version, raw = await inference.predict(preprocessed)

        assert model_version == "v1.0.0-linear-baseline"
        assert raw["method"] == "linear_trend"
        assert raw["slope_cm_per_day"] == pytest.approx(1.0)
        assert len(raw["projected_curve"]) == 3

    async def test_predict_falls_back_to_species_baseline_with_thin_history(self):
        inference = GrowthPredictionInference(prediction_logger=None)  # type: ignore[arg-type]
        preprocessed = {
            "history": [],
            "species_growth_curve_baseline": [
                {"days_since_planting": 0, "expected_height_cm": 5.0},
                {"days_since_planting": 100, "expected_height_cm": 50.0},
            ],
        }

        model_version, raw = await inference.predict(preprocessed)

        assert raw["method"] == "species_baseline"
        assert raw["current_height_cm"] == 5.0

    async def test_predict_reports_insufficient_data_with_no_history_and_no_baseline(self):
        inference = GrowthPredictionInference(prediction_logger=None)  # type: ignore[arg-type]

        _, raw = await inference.predict({"history": [], "species_growth_curve_baseline": []})

        assert raw["method"] == "insufficient_data"
        assert raw["projected_curve"] == []

    async def test_postprocess_returns_none_confidence_for_insufficient_data(self):
        inference = GrowthPredictionInference(prediction_logger=None)  # type: ignore[arg-type]

        confidence, explanation, result = await inference.postprocess(
            {"method": "insufficient_data", "data_points_used": 0, "projected_curve": []}
        )

        assert confidence is None
        assert "cannot project" in explanation.lower()

    async def test_postprocess_caps_linear_trend_confidence_below_one(self):
        inference = GrowthPredictionInference(prediction_logger=None)  # type: ignore[arg-type]

        confidence, _, _ = await inference.postprocess(
            {"method": "linear_trend", "data_points_used": 30, "r_squared": 1.0}
        )

        assert confidence is not None
        assert Decimal("0") < confidence <= Decimal("0.75")

    async def test_run_persists_a_growth_prediction_end_to_end(self, harness):
        inference = GrowthPredictionInference(prediction_logger=harness.prediction_logger)
        nursery_id = uuid.uuid4()

        prediction = await inference.run(
            nursery_id=nursery_id,
            features={
                "history": [
                    {"height_cm": 10.0, "days_since_planting": 0},
                    {"height_cm": 22.0, "days_since_planting": 14},
                ],
                "species_growth_curve_baseline": [],
            },
        )

        stored = await harness.ai_predictions.get_by_id(prediction.id)
        assert stored is not None
        assert stored.model_version == "v1.0.0-linear-baseline"
        assert stored.result["method"] == "linear_trend"


# ==============================================================================
# Survival Prediction -- weighted composite risk score
# ==============================================================================


class TestSurvivalPredictionInference:
    async def test_predict_scores_healthy_plant_low_risk(self):
        inference = SurvivalPredictionInference(prediction_logger=None)  # type: ignore[arg-type]

        _, raw = await inference.predict(
            {
                "health_trend": [{"status_label": "healthy", "recorded_at": "2026-01-01T00:00:00+00:00"}],
                "disease_report_severities": [],
                "disease_report_count": 0,
                "environmental_readings": [],
                "days_since_last_watering": 1,
            }
        )

        assert raw["risk_score"] < 25
        assert raw["factors"]["latest_health_status"] == "healthy"

    async def test_predict_scores_worst_case_inputs_as_critical_risk(self):
        # Regression test for a real bug found via live worst-case-input testing: with the
        # original `_SEVERITY_RISK["critical"] = 70`, the worst-case composite across all
        # four weighted factors topped out at 73 -- one point below `postprocess()`'s
        # "critical" risk_level threshold of 75, meaning a plant that is deceased, has a
        # critical-severity disease report, and hasn't been watered in weeks could never
        # actually be labeled "critical". Fixed by raising that constant to 80 (see its own
        # inline comment). This test locks in that the worst case now DOES reach "critical".
        inference = SurvivalPredictionInference(prediction_logger=None)  # type: ignore[arg-type]

        _, raw = await inference.predict(
            {
                "health_trend": [{"status_label": "deceased", "recorded_at": "2026-01-01T00:00:00+00:00"}],
                "disease_report_severities": ["critical"],
                "disease_report_count": 2,
                # Alternating 10C/30C readings -> pstdev=10 -> env_variance_risk hits its 30-point cap.
                "environmental_readings": [
                    {"temperature_celsius": 10.0}, {"temperature_celsius": 30.0},
                    {"temperature_celsius": 10.0}, {"temperature_celsius": 30.0},
                ],
                "days_since_last_watering": 30,
            }
        )
        _, _, result = await inference.postprocess(raw)

        assert raw["risk_score"] >= 75
        assert result["risk_level"] == "critical"

    async def test_predict_defaults_to_moderate_risk_with_no_recorded_status(self):
        inference = SurvivalPredictionInference(prediction_logger=None)  # type: ignore[arg-type]

        _, raw = await inference.predict(
            {
                "health_trend": [],
                "disease_report_severities": [],
                "disease_report_count": 0,
                "environmental_readings": [],
                "days_since_last_watering": None,
            }
        )

        assert raw["factors"]["latest_health_status"] is None
        assert raw["factors"]["health_risk_contribution"] == 40  # _UNKNOWN_HEALTH_RISK

    async def test_postprocess_labels_risk_levels_correctly(self):
        inference = SurvivalPredictionInference(prediction_logger=None)  # type: ignore[arg-type]

        _, _, low = await inference.postprocess(
            {"risk_score": 10.0, "data_points_used": 1, "factors": {"latest_health_status": None, "disease_report_count": 0, "days_since_last_watering": None}}
        )
        _, _, critical = await inference.postprocess(
            {"risk_score": 90.0, "data_points_used": 1, "factors": {"latest_health_status": None, "disease_report_count": 0, "days_since_last_watering": None}}
        )

        assert low["risk_level"] == "low"
        assert critical["risk_level"] == "critical"

    async def test_run_persists_a_survival_prediction_end_to_end(self, harness):
        inference = SurvivalPredictionInference(prediction_logger=harness.prediction_logger)
        nursery_id = uuid.uuid4()
        plant_id = uuid.uuid4()

        prediction = await inference.run(
            nursery_id=nursery_id,
            plant_id=plant_id,
            features={
                "health_trend": [{"status_label": "stressed", "recorded_at": "2026-01-01T00:00:00+00:00"}],
                "disease_report_severities": [],
                "disease_report_count": 0,
                "environmental_readings": [],
                "days_since_last_watering": 5,
            },
        )

        stored = await harness.ai_predictions.get_by_id(prediction.id)
        assert stored is not None
        assert stored.result["risk_level"] in {"low", "moderate", "high", "critical"}


# ==============================================================================
# Water Recommendation -- species baseline + rule adjustments
# ==============================================================================


class TestWaterRecommendationInference:
    async def test_predict_returns_no_baseline_method_when_species_baseline_missing(self):
        inference = WaterRecommendationInference(prediction_logger=None)  # type: ignore[arg-type]

        _, raw = await inference.predict(
            {"species_water_baseline_ml_per_week": None, "recent_soil_moisture": [], "recent_temperature": []}
        )

        assert raw["method"] == "no_species_baseline"
        assert raw["recommended_ml_per_week"] is None

    async def test_predict_increases_recommendation_for_low_soil_moisture(self):
        inference = WaterRecommendationInference(prediction_logger=None)  # type: ignore[arg-type]

        _, raw = await inference.predict(
            {
                "species_water_baseline_ml_per_week": 500,
                "recent_soil_moisture": [15.0, 20.0],
                "recent_temperature": [],
            }
        )

        assert raw["method"] == "species_baseline_adjusted"
        assert raw["recommended_ml_per_week"] > 500

    async def test_predict_decreases_recommendation_for_high_soil_moisture(self):
        inference = WaterRecommendationInference(prediction_logger=None)  # type: ignore[arg-type]

        _, raw = await inference.predict(
            {
                "species_water_baseline_ml_per_week": 500,
                "recent_soil_moisture": [85.0, 90.0],
                "recent_temperature": [],
            }
        )

        assert raw["recommended_ml_per_week"] < 500

    async def test_postprocess_returns_none_confidence_with_no_baseline(self):
        inference = WaterRecommendationInference(prediction_logger=None)  # type: ignore[arg-type]

        confidence, explanation, _ = await inference.postprocess(
            {"method": "no_species_baseline", "recommended_ml_per_week": None, "data_points_used": 0}
        )

        assert confidence is None
        assert "cannot generate" in explanation.lower()

    async def test_run_persists_a_water_recommendation_end_to_end(self, harness):
        inference = WaterRecommendationInference(prediction_logger=harness.prediction_logger)
        nursery_id = uuid.uuid4()
        plant_id = uuid.uuid4()

        prediction = await inference.run(
            nursery_id=nursery_id,
            plant_id=plant_id,
            features={
                "species_water_baseline_ml_per_week": 400,
                "recent_soil_moisture": [40.0],
                "recent_temperature": [22.0],
            },
        )

        stored = await harness.ai_predictions.get_by_id(prediction.id)
        assert stored is not None
        assert stored.result["method"] == "species_baseline_adjusted"


# ==============================================================================
# Revenue Forecast -- seasonal-naive baseline, Branch-scoped
# ==============================================================================


class TestRevenueForecastInference:
    async def test_predict_reports_insufficient_data_below_minimum_history(self):
        inference = RevenueForecastInference(prediction_logger=None)  # type: ignore[arg-type]

        _, raw = await inference.predict({"daily_revenue": [{"date": "2026-01-01", "revenue": 100.0}]})

        assert raw["method"] == "insufficient_data"

    async def test_predict_produces_a_forecast_with_enough_history(self):
        inference = RevenueForecastInference(prediction_logger=None)  # type: ignore[arg-type]
        daily = [{"date": f"2026-01-{d:02d}", "revenue": 100.0 + d} for d in range(1, 15)]

        _, raw = await inference.predict({"daily_revenue": daily})

        assert raw["method"] == "seasonal_naive"
        assert len(raw["forecast"]) == 14
        for point in raw["forecast"]:
            assert point["lower_bound"] <= point["projected_revenue"] <= point["upper_bound"]

    async def test_postprocess_returns_none_confidence_for_insufficient_data(self):
        inference = RevenueForecastInference(prediction_logger=None)  # type: ignore[arg-type]

        confidence, explanation, _ = await inference.postprocess(
            {"method": "insufficient_data", "data_points_used": 3}
        )

        assert confidence is None
        assert "at least" in explanation.lower()

    async def test_run_persists_a_branch_scoped_revenue_forecast_end_to_end(self, harness):
        inference = RevenueForecastInference(prediction_logger=harness.prediction_logger)
        nursery_id = uuid.uuid4()
        branch_id = uuid.uuid4()
        daily = [{"date": f"2026-01-{d:02d}", "revenue": 100.0 + d} for d in range(1, 15)]
        before = len(harness.domain_events.events)

        prediction = await inference.run(
            nursery_id=nursery_id, branch_id=branch_id, features={"daily_revenue": daily}
        )

        stored = await harness.ai_predictions.get_by_id(prediction.id)
        assert stored is not None
        assert stored.branch_id == branch_id
        assert stored.plant_id is None
        events = harness.domain_events.events[before:]
        assert any(
            e.event_type == "ai.prediction_generated_for_branch" and e.aggregate_id == branch_id for e in events
        )
