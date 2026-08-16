"""
Unit tests for Module 10's `RecommendationEngine` (FR-8.6). Pure,
deterministic scoring/grouping over already-persisted `AIPrediction`
rows -- no repository or harness needed, matching the class's own
docstring ("real, deterministic, over real AIPrediction.result data").
"""
from __future__ import annotations

import uuid

import pytest

from app.ai.recommendation_engine.engine import RecommendationEngine
from app.db.enums import AIPredictionType, AIRecommendationStatus
from app.models.ai import AIPrediction

pytestmark = pytest.mark.unit


def _survival_prediction(*, nursery_id: uuid.UUID, branch_id: uuid.UUID, risk_score: float, plant_id=None) -> AIPrediction:
    return AIPrediction(
        id=uuid.uuid4(), nursery_id=nursery_id, branch_id=branch_id, plant_id=plant_id or uuid.uuid4(),
        prediction_type=AIPredictionType.SURVIVAL_PREDICTION, model_version="v1.0.0-weighted-risk-baseline",
        result={"risk_score": risk_score, "risk_level": "high" if risk_score >= 60 else "moderate"},
    )


class TestRecommendationEngine:
    def test_returns_empty_list_when_no_predictions_are_at_risk(self):
        engine = RecommendationEngine()
        nursery_id, branch_id = uuid.uuid4(), uuid.uuid4()
        predictions = [_survival_prediction(nursery_id=nursery_id, branch_id=branch_id, risk_score=10.0)]

        recommendations = engine.generate_survival_risk_recommendations(
            nursery_id=nursery_id, branch_id=branch_id, predictions=predictions
        )

        assert recommendations == []

    def test_returns_empty_list_for_no_predictions_at_all(self):
        engine = RecommendationEngine()
        nursery_id, branch_id = uuid.uuid4(), uuid.uuid4()

        recommendations = engine.generate_survival_risk_recommendations(
            nursery_id=nursery_id, branch_id=branch_id, predictions=[]
        )

        assert recommendations == []

    def test_produces_a_high_priority_recommendation_for_high_risk_plants(self):
        engine = RecommendationEngine()
        nursery_id, branch_id = uuid.uuid4(), uuid.uuid4()
        predictions = [
            _survival_prediction(nursery_id=nursery_id, branch_id=branch_id, risk_score=70.0),
            _survival_prediction(nursery_id=nursery_id, branch_id=branch_id, risk_score=65.0),
        ]

        recommendations = engine.generate_survival_risk_recommendations(
            nursery_id=nursery_id, branch_id=branch_id, predictions=predictions
        )

        assert len(recommendations) == 1
        rec = recommendations[0]
        assert rec.priority == "high"
        assert "2 plant(s)" in rec.summary
        assert rec.status == AIRecommendationStatus.NEW
        assert rec.nursery_id == nursery_id
        assert rec.branch_id == branch_id

    def test_produces_a_medium_priority_recommendation_for_moderate_risk_plants(self):
        engine = RecommendationEngine()
        nursery_id, branch_id = uuid.uuid4(), uuid.uuid4()
        predictions = [_survival_prediction(nursery_id=nursery_id, branch_id=branch_id, risk_score=45.0)]

        recommendations = engine.generate_survival_risk_recommendations(
            nursery_id=nursery_id, branch_id=branch_id, predictions=predictions
        )

        assert len(recommendations) == 1
        assert recommendations[0].priority == "medium"

    def test_produces_both_high_and_medium_recommendations_when_both_tiers_present(self):
        engine = RecommendationEngine()
        nursery_id, branch_id = uuid.uuid4(), uuid.uuid4()
        predictions = [
            _survival_prediction(nursery_id=nursery_id, branch_id=branch_id, risk_score=80.0),
            _survival_prediction(nursery_id=nursery_id, branch_id=branch_id, risk_score=45.0),
            _survival_prediction(nursery_id=nursery_id, branch_id=branch_id, risk_score=5.0),  # below threshold, excluded
        ]

        recommendations = engine.generate_survival_risk_recommendations(
            nursery_id=nursery_id, branch_id=branch_id, predictions=predictions
        )

        priorities = {r.priority for r in recommendations}
        assert priorities == {"high", "medium"}

    def test_deep_link_points_at_the_highest_scoring_plant_in_each_tier(self):
        engine = RecommendationEngine()
        nursery_id, branch_id = uuid.uuid4(), uuid.uuid4()
        worst_plant_id = uuid.uuid4()
        predictions = [
            _survival_prediction(nursery_id=nursery_id, branch_id=branch_id, risk_score=61.0),
            _survival_prediction(nursery_id=nursery_id, branch_id=branch_id, risk_score=95.0, plant_id=worst_plant_id),
        ]

        recommendations = engine.generate_survival_risk_recommendations(
            nursery_id=nursery_id, branch_id=branch_id, predictions=predictions
        )

        assert recommendations[0].deep_link == f"/plants/{worst_plant_id}"

    def test_treats_a_missing_risk_score_as_zero_not_a_crash(self):
        engine = RecommendationEngine()
        nursery_id, branch_id = uuid.uuid4(), uuid.uuid4()
        prediction = AIPrediction(
            id=uuid.uuid4(), nursery_id=nursery_id, branch_id=branch_id, plant_id=uuid.uuid4(),
            prediction_type=AIPredictionType.SURVIVAL_PREDICTION, model_version="v1.0.0-weighted-risk-baseline",
            result={},  # no risk_score key at all
        )

        recommendations = engine.generate_survival_risk_recommendations(
            nursery_id=nursery_id, branch_id=branch_id, predictions=[prediction]
        )

        assert recommendations == []
