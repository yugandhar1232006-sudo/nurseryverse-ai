"""
FR-8.6 -- AI Recommendation Engine: "surfaces prioritized, explained
action suggestions (e.g., 'these 12 plants are at elevated survival
risk -- inspect this week')."

Not an `InferenceBase` subclass -- it doesn't produce an `AIPrediction`
(there is no `"recommendation_engine"` value in `AIPredictionType`,
deliberately: this module *consumes* other modules' already-persisted
predictions rather than making one of its own). Feature-weighted scoring
(real, deterministic, over real `AIPrediction.result` data) -- the "LLM
narrative" half docs/architecture/06-ai-architecture.md §1's module table
mentions is an optional richer-explanation layer that could sit on top of
this in a future iteration; it is not required to satisfy FR-8.6's letter
("prioritized, explained action suggestions"), which this class already
produces deterministically and testably without a live LLM call.

`generate_survival_risk_recommendations` is invoked by
`AIRecommendationService` (app/services/ai_recommendation_service.py),
either on-demand (`POST /ai/recommendations/refresh`, permission-gated)
or from a scheduled aggregation job -- both call sites go through the
identical method, matching this codebase's established "no separate code
path for on-demand vs. triggered invocation" convention (doc §6).
"""
from __future__ import annotations

import uuid
from typing import Any

from app.db.enums import AIRecommendationStatus
from app.models.ai import AIPrediction, AIRecommendation

MODEL_VERSION = "v1.0.0-rule-baseline"
HIGH_RISK_THRESHOLD = 60
ELEVATED_RISK_THRESHOLD = 40


class RecommendationEngine:
    def generate_survival_risk_recommendations(
        self, *, nursery_id: uuid.UUID, branch_id: uuid.UUID, predictions: list[AIPrediction]
    ) -> list[AIRecommendation]:
        """
        `predictions` should be the latest Survival Prediction row per
        plant for this branch (the caller is responsible for that
        de-duplication -- this method only scores/groups what it's
        given, matching every other "assemble first, score second"
        boundary in this codebase).
        """
        scored = [(p, _risk_score(p)) for p in predictions]
        at_risk = [(p, score) for p, score in scored if score >= ELEVATED_RISK_THRESHOLD]
        if not at_risk:
            return []

        high = [(p, score) for p, score in at_risk if score >= HIGH_RISK_THRESHOLD]
        moderate = [(p, score) for p, score in at_risk if score < HIGH_RISK_THRESHOLD]

        recommendations: list[AIRecommendation] = []
        if high:
            top = max(high, key=lambda item: item[1])
            recommendations.append(
                AIRecommendation(
                    nursery_id=nursery_id,
                    branch_id=branch_id,
                    source_prediction_id=top[0].id,
                    priority="high",
                    summary=f"{len(high)} plant(s) at elevated survival risk -- inspect this week",
                    explanation=(
                        f"{len(high)} plant(s) scored {HIGH_RISK_THRESHOLD}+ / 100 on their latest Survival "
                        f"Prediction run (highest: {round(top[1], 1)}/100). Immediate inspection recommended."
                    ),
                    deep_link=f"/plants/{top[0].plant_id}" if top[0].plant_id else None,
                    status=AIRecommendationStatus.NEW,
                    model_version=MODEL_VERSION,
                )
            )
        if moderate:
            top = max(moderate, key=lambda item: item[1])
            recommendations.append(
                AIRecommendation(
                    nursery_id=nursery_id,
                    branch_id=branch_id,
                    source_prediction_id=top[0].id,
                    priority="medium",
                    summary=f"{len(moderate)} plant(s) showing early survival risk signs",
                    explanation=(
                        f"{len(moderate)} plant(s) scored between {ELEVATED_RISK_THRESHOLD} and "
                        f"{HIGH_RISK_THRESHOLD} / 100 on their latest Survival Prediction run "
                        f"(highest: {round(top[1], 1)}/100). A routine check is recommended."
                    ),
                    deep_link=f"/plants/{top[0].plant_id}" if top[0].plant_id else None,
                    status=AIRecommendationStatus.NEW,
                    model_version=MODEL_VERSION,
                )
            )
        return recommendations


def _risk_score(prediction: AIPrediction) -> float:
    result: dict[str, Any] = prediction.result or {}
    score = result.get("risk_score")
    return float(score) if score is not None else 0.0
