"""
FR-8.4 -- AI Water Recommendation: "producing a recommended watering
schedule per plant or per zone."

Same versioning/no-training-data reasoning as growth_prediction/
inference.py's module docstring. docs/architecture/06-ai-architecture.md
§1 names "scikit-learn + rule layer" as this module's eventual framework
-- this implements the real, working "rule layer" half of that today:
`species.water_baseline_ml_per_week` adjusted by recent soil-moisture and
temperature readings, real math over real repository data, explicitly
versioned as `v1.0.0-rule-baseline` so a later scikit-learn model can
layer on top (or replace this) without any caller-facing change.
"""
from __future__ import annotations

import statistics
from decimal import Decimal
from typing import Any

from app.ai.common.inference_base import InferenceBase
from app.db.enums import AIPredictionType

MODEL_VERSION = "v1.0.0-rule-baseline"

# Bounds on how far a single reading-based adjustment can move the
# species baseline -- keeps the recommendation from swinging wildly off a
# single outlier reading.
_MIN_ADJUSTMENT = 0.5
_MAX_ADJUSTMENT = 1.75


class WaterRecommendationInference(InferenceBase):
    prediction_type = AIPredictionType.WATER_RECOMMENDATION
    capability = "water_recommendation"

    async def preprocess(self, features: dict[str, Any]) -> dict[str, Any]:
        return features

    async def predict(self, preprocessed: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        baseline = preprocessed.get("species_water_baseline_ml_per_week")
        soil_moisture_readings = preprocessed.get("recent_soil_moisture", [])
        temp_readings = preprocessed.get("recent_temperature", [])

        avg_soil_moisture = statistics.fmean(soil_moisture_readings) if soil_moisture_readings else None
        avg_temp = statistics.fmean(temp_readings) if temp_readings else None

        if baseline is None:
            return MODEL_VERSION, {
                "method": "no_species_baseline",
                "recommended_ml_per_week": None,
                "avg_soil_moisture_percent": avg_soil_moisture,
                "avg_temperature_celsius": avg_temp,
                "data_points_used": len(soil_moisture_readings) + len(temp_readings),
            }

        adjustment = 1.0
        reasons: list[str] = []
        if avg_soil_moisture is not None:
            if avg_soil_moisture < 30:
                adjustment += 0.25
                reasons.append(f"low recent soil moisture ({round(avg_soil_moisture, 1)}%) -- increasing")
            elif avg_soil_moisture > 70:
                adjustment -= 0.20
                reasons.append(f"high recent soil moisture ({round(avg_soil_moisture, 1)}%) -- decreasing")
        if avg_temp is not None:
            if avg_temp > 28:
                adjustment += 0.15
                reasons.append(f"warm recent temperatures ({round(avg_temp, 1)}°C) -- increasing")
            elif avg_temp < 15:
                adjustment -= 0.10
                reasons.append(f"cool recent temperatures ({round(avg_temp, 1)}°C) -- decreasing")
        adjustment = max(_MIN_ADJUSTMENT, min(_MAX_ADJUSTMENT, adjustment))

        return MODEL_VERSION, {
            "method": "species_baseline_adjusted",
            "baseline_ml_per_week": baseline,
            "adjustment_factor": round(adjustment, 3),
            "adjustment_reasons": reasons,
            "recommended_ml_per_week": round(baseline * adjustment, 1),
            "avg_soil_moisture_percent": round(avg_soil_moisture, 1) if avg_soil_moisture is not None else None,
            "avg_temperature_celsius": round(avg_temp, 1) if avg_temp is not None else None,
            "data_points_used": len(soil_moisture_readings) + len(temp_readings),
        }

    async def postprocess(self, raw_result: dict[str, Any]) -> tuple[Decimal | None, str | None, dict[str, Any]]:
        if raw_result["method"] == "no_species_baseline":
            return None, "No species water baseline configured -- cannot generate a recommendation.", raw_result

        n = raw_result["data_points_used"]
        confidence = Decimal(str(round(min(0.65, 0.35 + 0.03 * n), 4)))
        reasons = raw_result["adjustment_reasons"]
        explanation = f"Recommended {raw_result['recommended_ml_per_week']} mL/week, from a species baseline of {raw_result['baseline_ml_per_week']} mL/week"
        explanation += f" ({'; '.join(reasons)})." if reasons else " (no adjustment -- recent readings within normal range)."
        return confidence, explanation, raw_result
