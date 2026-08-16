"""
FR-8.5 -- AI Revenue Forecast: "runs at the Branch and Org level,
producing a projected revenue curve with a confidence interval."

Same versioning/no-training-data reasoning as growth_prediction/
inference.py's module docstring. docs/architecture/06-ai-architecture.md
§1 names Prophet as this module's eventual framework -- this implements a
real, working "seasonal naive" forecast (day-of-week seasonality +
a 95% confidence band from the historical standard deviation, both
standard, legitimate time-series baselines a real Prophet model is
routinely benchmarked against, not a toy stand-in) as `v1.0.0-seasonal-
naive-baseline`, swappable for a trained Prophet model later without any
caller-facing change.

This is the one prediction module with no `plant_id` -- `aggregate_type`
in the domain event this produces is `"Branch"`, not `"Plant"` (see
app/domain_events/events.py's `AIPredictionGeneratedForBranch`).
"""
from __future__ import annotations

import statistics
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from app.ai.common.inference_base import InferenceBase
from app.db.enums import AIPredictionType

MODEL_VERSION = "v1.0.0-seasonal-naive-baseline"
_MIN_HISTORY_DAYS = 7
_FORECAST_HORIZON_DAYS = 14
_CONFIDENCE_Z = 1.96  # ~95% interval, standard normal-approximation z-score


class RevenueForecastInference(InferenceBase):
    prediction_type = AIPredictionType.REVENUE_FORECAST
    capability = "revenue_forecast"

    async def preprocess(self, features: dict[str, Any]) -> dict[str, Any]:
        return features

    async def predict(self, preprocessed: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        daily = preprocessed.get("daily_revenue", [])
        if len(daily) < _MIN_HISTORY_DAYS:
            return MODEL_VERSION, {"method": "insufficient_data", "data_points_used": len(daily), "forecast": []}

        revenues = [d["revenue"] for d in daily]
        overall_mean = statistics.fmean(revenues)
        overall_stdev = statistics.pstdev(revenues) if len(revenues) > 1 else 0.0

        by_weekday: dict[int, list[float]] = {}
        for d in daily:
            weekday = date.fromisoformat(d["date"]).weekday()
            by_weekday.setdefault(weekday, []).append(d["revenue"])
        weekday_means = {wd: statistics.fmean(vals) for wd, vals in by_weekday.items()}

        last_date = date.fromisoformat(daily[-1]["date"])
        forecast = []
        for i in range(1, _FORECAST_HORIZON_DAYS + 1):
            forecast_date = last_date + timedelta(days=i)
            point = weekday_means.get(forecast_date.weekday(), overall_mean)
            forecast.append(
                {
                    "date": forecast_date.isoformat(),
                    "projected_revenue": round(point, 2),
                    "lower_bound": round(max(0.0, point - _CONFIDENCE_Z * overall_stdev), 2),
                    "upper_bound": round(point + _CONFIDENCE_Z * overall_stdev, 2),
                }
            )

        return MODEL_VERSION, {
            "method": "seasonal_naive",
            "data_points_used": len(daily),
            "overall_mean_daily_revenue": round(overall_mean, 2),
            "overall_stdev_daily_revenue": round(overall_stdev, 2),
            "forecast": forecast,
        }

    async def postprocess(self, raw_result: dict[str, Any]) -> tuple[Decimal | None, str | None, dict[str, Any]]:
        if raw_result["method"] == "insufficient_data":
            n = raw_result["data_points_used"]
            return (
                None,
                f"Only {n} day(s) of sales history -- at least {_MIN_HISTORY_DAYS} are needed for a seasonal forecast.",
                raw_result,
            )

        n = raw_result["data_points_used"]
        # More historical days raise confidence, capped well below 1.0 -- a seasonal-naive baseline, not a
        # validated Prophet model, should never claim near-certainty about future revenue.
        confidence = Decimal(str(round(min(0.60, 0.20 + 0.01 * n), 4)))
        explanation = (
            f"Seasonal-naive forecast over {n} days of history "
            f"(mean daily revenue ${raw_result['overall_mean_daily_revenue']}, "
            f"±${round(_CONFIDENCE_Z * raw_result['overall_stdev_daily_revenue'], 2)} at ~95% confidence), "
            f"projecting {_FORECAST_HORIZON_DAYS} days ahead."
        )
        return confidence, explanation, raw_result
