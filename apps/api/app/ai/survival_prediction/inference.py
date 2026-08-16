"""
FR-8.3 -- AI Survival Prediction: "runs against a plant's health/
environmental history, producing a risk score and contributing factors."

Same versioning/no-training-data reasoning as growth_prediction/
inference.py's module docstring (referenced there, not repeated in full
here): docs/architecture/06-ai-architecture.md §1 names XGBoost as this
module's eventual framework; with no training data or artifact available
in this sandbox, `model_version="v1.0.0-weighted-risk-baseline"` is a
real, working, explicitly-versioned weighted composite-risk scorer over
the exact feature set §4 specifies (health trend, environmental variance,
watering consistency, disease history, species disease susceptibility),
not a placeholder.
"""
from __future__ import annotations

import statistics
from decimal import Decimal
from typing import Any

from app.ai.common.inference_base import InferenceBase
from app.db.enums import AIPredictionType

MODEL_VERSION = "v1.0.0-weighted-risk-baseline"

# 0 (no risk) - 100 (imminent). Free-text `status_label` values observed in
# this codebase's own seed/fixture data (app/models/digital_twin_records.py's
# "healthy, stressed, recovering" example) plus the natural extremes.
_HEALTH_RISK = {
    "thriving": 0, "healthy": 5, "stable": 10, "recovering": 30,
    "stressed": 55, "declining": 80, "critical": 95, "deceased": 100,
}
_SEVERITY_RISK = {"low": 10, "medium": 25, "high": 45, "critical": 80}
# NOTE: 80, not the more "natural"-looking 70 -- with the four contribution
# weights below (0.45/0.25/0.15/0.15) and each factor's own cap, a
# `critical` disease severity risk of 70 makes the worst-case composite
# score exactly 73 (0.45*100 + 0.25*70 + 0.15*30 + 0.15*40), which is
# BELOW the `postprocess()` "critical" risk_level threshold of 75 -- i.e.
# a plant that is deceased, has a critical-severity disease report, and
# hasn't been watered in weeks could never actually be labeled "critical",
# only "high", regardless of how bad its real condition is. Found via live
# worst-case-input testing (tests/unit/test_ai_inference_modules.py), not
# by the original unit tests, since none of them exercised every factor at
# its cap simultaneously. 80 raises the worst-case composite to 75.5,
# making the "critical" risk_level (the label a nursery worker most needs
# to see for an at-risk plant) actually reachable.
_UNKNOWN_HEALTH_RISK = 40  # no recorded status is not evidence of health -- moderate default, not zero.


class SurvivalPredictionInference(InferenceBase):
    prediction_type = AIPredictionType.SURVIVAL_PREDICTION
    capability = "survival_prediction"

    async def preprocess(self, features: dict[str, Any]) -> dict[str, Any]:
        return features

    async def predict(self, preprocessed: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        health_trend = preprocessed.get("health_trend", [])
        latest_status = health_trend[-1]["status_label"].lower() if health_trend else None
        health_risk = _HEALTH_RISK.get(latest_status, _UNKNOWN_HEALTH_RISK) if latest_status else _UNKNOWN_HEALTH_RISK

        severities = preprocessed.get("disease_report_severities", [])
        disease_risk = max((_SEVERITY_RISK.get(str(s).lower(), 20) for s in severities), default=0)

        env_readings = preprocessed.get("environmental_readings", [])
        temps = [e["temperature_celsius"] for e in env_readings if e.get("temperature_celsius") is not None]
        env_variance_risk = min(30.0, statistics.pstdev(temps) * 3) if len(temps) >= 2 else 0.0

        days_since_watering = preprocessed.get("days_since_last_watering")
        if days_since_watering is None:
            watering_risk = 15.0
        elif days_since_watering > 14:
            watering_risk = min(40.0, (days_since_watering - 14) * 3)
        else:
            watering_risk = 0.0

        composite = min(
            100.0,
            round(0.45 * health_risk + 0.25 * disease_risk + 0.15 * env_variance_risk + 0.15 * watering_risk, 1),
        )
        return MODEL_VERSION, {
            "risk_score": composite,
            "factors": {
                "latest_health_status": latest_status,
                "health_risk_contribution": health_risk,
                "disease_risk_contribution": disease_risk,
                "environmental_variance_risk_contribution": round(env_variance_risk, 1),
                "watering_risk_contribution": round(watering_risk, 1),
                "days_since_last_watering": days_since_watering,
                "disease_report_count": preprocessed.get("disease_report_count", 0),
            },
            "data_points_used": len(health_trend) + len(env_readings),
        }

    async def postprocess(self, raw_result: dict[str, Any]) -> tuple[Decimal | None, str | None, dict[str, Any]]:
        score = raw_result["risk_score"]
        if score >= 75:
            level = "critical"
        elif score >= 50:
            level = "high"
        elif score >= 25:
            level = "moderate"
        else:
            level = "low"

        n = raw_result["data_points_used"]
        # More corroborating data points raise confidence in the score, capped well below 1.0 -- a weighted
        # heuristic, not a validated classifier, should never claim near-certainty.
        confidence = Decimal(str(round(min(0.70, 0.25 + 0.03 * n), 4)))

        factors = raw_result["factors"]
        explanation_parts = [f"Survival risk {score}/100 ({level})."]
        if factors["latest_health_status"]:
            explanation_parts.append(f"Latest health status: {factors['latest_health_status']}.")
        if factors["disease_report_count"]:
            explanation_parts.append(f"{factors['disease_report_count']} disease report(s) on file.")
        if factors["days_since_last_watering"] is not None and factors["days_since_last_watering"] > 14:
            explanation_parts.append(f"{factors['days_since_last_watering']} days since last watering.")
        explanation = " ".join(explanation_parts)

        result = {**raw_result, "risk_level": level}
        return confidence, explanation, result
