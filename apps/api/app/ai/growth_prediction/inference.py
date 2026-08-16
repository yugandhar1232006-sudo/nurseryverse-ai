"""
FR-8.2 -- AI Growth Prediction: "runs against a plant's growth timeline
and species baseline, producing a projected growth curve."

VERSIONING NOTE (applies identically to survival_prediction/water_
recommendation/revenue_forecast -- stated once here, referenced by the
other three). docs/architecture/06-ai-architecture.md §1 names "Prophet +
gradient boosting fallback" as this module's eventual framework. This
sandbox has no training data, no object-storage-hosted model artifact,
and no `ModelRegistry.get()` cache-hit for any capability (see
model_registry.py's own docstring) -- there is nothing to fall back
*from*. Rather than fake a Prophet/GBM result with static numbers (which
this project's own governing instructions forbid), this module implements
the "fallback" *itself*, for real: a least-squares linear-trend fit over
`GrowthTimeline` history when at least two data points exist, falling
back further to `species.growth_curve_baseline` interpolation when they
don't. `model_version="v1.0.0-linear-baseline"` records exactly which
method produced a given stored prediction (docs §10's own "model
versioning" contract), and is what a later, real Prophet/GBM model would
increment when it replaces this -- callers never change, since both are
reached through the identical `InferenceBase.run()` contract.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.ai.common.inference_base import InferenceBase
from app.db.enums import AIPredictionType

MODEL_VERSION = "v1.0.0-linear-baseline"
_PROJECTION_HORIZONS_DAYS = (30, 60, 90)


class GrowthPredictionInference(InferenceBase):
    prediction_type = AIPredictionType.GROWTH_PREDICTION
    capability = "growth_prediction"

    async def preprocess(self, features: dict[str, Any]) -> dict[str, Any]:
        history = [h for h in features.get("history", []) if h.get("height_cm") is not None and h.get("days_since_planting") is not None]
        return {
            "history": history,
            "species_growth_curve_baseline": features.get("species_growth_curve_baseline") or [],
        }

    async def predict(self, preprocessed: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        history = preprocessed["history"]
        if len(history) >= 2:
            xs = [h["days_since_planting"] for h in history]
            ys = [h["height_cm"] for h in history]
            slope, intercept, r_squared = _linear_fit(xs, ys)
            last_day = xs[-1]
            projections = [
                {"days_since_planting": last_day + h, "projected_height_cm": round(slope * (last_day + h) + intercept, 2)}
                for h in _PROJECTION_HORIZONS_DAYS
            ]
            return MODEL_VERSION, {
                "method": "linear_trend",
                "data_points_used": len(history),
                "current_height_cm": ys[-1],
                "slope_cm_per_day": round(slope, 4),
                "r_squared": round(r_squared, 4),
                "projected_curve": projections,
            }

        baseline = preprocessed["species_growth_curve_baseline"]
        if baseline:
            sorted_baseline = sorted(baseline, key=lambda p: p["days_since_planting"])
            current_day = history[-1]["days_since_planting"] if history else 0
            current_height = _interpolate(sorted_baseline, current_day)
            projections = [
                {"days_since_planting": current_day + h, "projected_height_cm": _interpolate(sorted_baseline, current_day + h)}
                for h in _PROJECTION_HORIZONS_DAYS
            ]
            return MODEL_VERSION, {
                "method": "species_baseline",
                "data_points_used": len(history),
                "current_height_cm": current_height,
                "projected_curve": projections,
            }

        return MODEL_VERSION, {"method": "insufficient_data", "data_points_used": len(history), "projected_curve": []}

    async def postprocess(self, raw_result: dict[str, Any]) -> tuple[Decimal | None, str | None, dict[str, Any]]:
        method = raw_result["method"]
        if method == "linear_trend":
            # More data points and a tighter fit both raise confidence; capped well below 1.0 -- this is a linear
            # heuristic, not a validated ML model, and should never claim more certainty than that.
            n = raw_result["data_points_used"]
            r_squared = raw_result["r_squared"]
            confidence = Decimal(str(round(min(0.75, 0.3 + 0.05 * n) * max(0.4, r_squared), 4)))
            explanation = (
                f"Linear trend fit over {n} growth measurements (R²={r_squared}); "
                f"projecting {', '.join(str(h) for h in _PROJECTION_HORIZONS_DAYS)} days ahead."
            )
        elif method == "species_baseline":
            confidence = Decimal("0.30")
            explanation = (
                f"Insufficient plant-specific history ({raw_result['data_points_used']} measurement(s)) -- "
                "projected from this species' typical growth curve baseline instead."
            )
        else:
            confidence = None
            explanation = "No growth measurements and no species growth curve baseline available -- cannot project."
        return confidence, explanation, raw_result


def _linear_fit(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    ss_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
    ss_xx = sum((x - mean_x) ** 2 for x in xs)
    if ss_xx == 0:
        return 0.0, mean_y, 0.0
    slope = ss_xy / ss_xx
    intercept = mean_y - slope * mean_x
    ss_tot = sum((y - mean_y) ** 2 for y in ys)
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys, strict=True))
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
    return slope, intercept, r_squared


def _interpolate(sorted_points: list[dict[str, Any]], day: float) -> float:
    if not sorted_points:
        return 0.0
    if day <= sorted_points[0]["days_since_planting"]:
        return sorted_points[0]["expected_height_cm"]
    if day >= sorted_points[-1]["days_since_planting"]:
        return sorted_points[-1]["expected_height_cm"]
    for a, b in zip(sorted_points, sorted_points[1:], strict=False):
        if a["days_since_planting"] <= day <= b["days_since_planting"]:
            span = b["days_since_planting"] - a["days_since_planting"]
            if span == 0:
                return a["expected_height_cm"]
            ratio = (day - a["days_since_planting"]) / span
            return round(a["expected_height_cm"] + ratio * (b["expected_height_cm"] - a["expected_height_cm"]), 2)
    return sorted_points[-1]["expected_height_cm"]
