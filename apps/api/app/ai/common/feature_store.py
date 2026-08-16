"""
`FeatureStore` -- assembles module-specific feature vectors from the
Digital Twin's raw history tables, per docs/architecture/06-ai-
architecture.md §4 (Feature Engineering). Every method takes an
already-fetched `Plant`/`branch_id`/`nursery_id` (never a bare, caller-
supplied id it would have to trust) -- "all feature assembly is
tenant-scoped by construction... never a global query," per that same
section -- matching the "fetch-then-authorize" discipline every route in
this codebase already follows: by the time a caller reaches here, the
plant/branch has already been fetched and authorized against the
requesting user's real tenant.

Pure data assembly, no inference logic -- this class never calls
`InferenceBase.predict()` or persists anything. It reads through the same
repository Protocol interfaces every other service in this codebase uses,
so it is unit-testable against the in-memory Fakes.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.models.catalog import Species
from app.models.plants import Plant
from app.repositories.interfaces import (
    DiseaseReportRepository,
    EnvironmentalReadingRepository,
    FertilizerLogRepository,
    GrowthTimelineRepository,
    HealthHistoryRepository,
    SaleRepository,
    SpeciesRepository,
    WateringLogRepository,
)

_HISTORY_LIMIT = 30  # recent-history window every assembly method reads -- enough for a meaningful trend without unbounded growth as a plant ages.


class FeatureStore:
    def __init__(
        self,
        *,
        species_repo: SpeciesRepository,
        growth_repo: GrowthTimelineRepository,
        health_repo: HealthHistoryRepository,
        watering_repo: WateringLogRepository,
        fertilizer_repo: FertilizerLogRepository,
        environmental_repo: EnvironmentalReadingRepository,
        disease_repo: DiseaseReportRepository,
        sale_repo: SaleRepository,
    ) -> None:
        self._species = species_repo
        self._growth = growth_repo
        self._health = health_repo
        self._watering = watering_repo
        self._fertilizer = fertilizer_repo
        self._environmental = environmental_repo
        self._disease = disease_repo
        self._sales = sale_repo

    async def _species_for(self, plant: Plant) -> Species | None:
        return await self._species.get_by_id(plant.species_id)

    async def assemble_growth_features(self, plant: Plant) -> dict[str, Any]:
        """Growth Prediction: `growth_timeline` entries plus `species.growth_curve_baseline` when plant-specific history is thin (doc §4)."""
        entries, _ = await self._growth.list_for_plant(plant.id, offset=0, limit=_HISTORY_LIMIT)
        species = await self._species_for(plant)
        history = [
            {
                "height_cm": float(e.height_cm) if e.height_cm is not None else None,
                "spread_cm": float(e.spread_cm) if e.spread_cm is not None else None,
                "growth_stage": e.growth_stage,
                "recorded_at": e.recorded_at.isoformat() if e.recorded_at else None,
                "days_since_planting": _days_since(plant.planted_at, e.recorded_at),
            }
            for e in entries
        ]
        return {
            "plant_id": str(plant.id),
            "planted_at": plant.planted_at.isoformat() if plant.planted_at else None,
            "history": sorted((h for h in history if h["recorded_at"]), key=lambda h: h["recorded_at"]),
            "history_count": len(history),
            "species_growth_curve_baseline": (species.growth_curve_baseline if species else None) or [],
        }

    async def assemble_survival_features(self, plant: Plant) -> dict[str, Any]:
        """
        Survival Prediction: recent health-status trend, environmental
        variance, watering consistency (days-since-last vs. species
        baseline interval), disease-report count/severity history, and
        `species.disease_susceptibility` (doc §4's exact composite list).
        """
        health_entries, _ = await self._health.list_for_plant(plant.id, offset=0, limit=_HISTORY_LIMIT)
        watering_entries, _ = await self._watering.list_for_plant(plant.id, offset=0, limit=_HISTORY_LIMIT)
        env_entries, _ = await self._environmental.list_for_plant(plant.id, offset=0, limit=_HISTORY_LIMIT)
        disease_reports = await self._disease.list_for_plant(plant.id)
        species = await self._species_for(plant)

        now = datetime.now(timezone.utc)
        last_watering = max((w.recorded_at for w in watering_entries if w.recorded_at), default=None)
        days_since_watering = (now - last_watering).days if last_watering else None

        return {
            "plant_id": str(plant.id),
            "health_trend": [
                {"status_label": h.status_label, "recorded_at": h.recorded_at.isoformat() if h.recorded_at else None}
                for h in health_entries
            ],
            "days_since_last_watering": days_since_watering,
            "watering_event_count": len(watering_entries),
            "environmental_readings": [
                {
                    "temperature_celsius": float(e.temperature_celsius) if e.temperature_celsius is not None else None,
                    "humidity_percent": float(e.humidity_percent) if e.humidity_percent is not None else None,
                    "soil_moisture_percent": (
                        float(e.soil_moisture_percent) if e.soil_moisture_percent is not None else None
                    ),
                }
                for e in env_entries
            ],
            "disease_report_count": len(disease_reports),
            "disease_report_severities": [str(r.severity.value) for r in disease_reports if r.severity is not None],
            "species_disease_susceptibility": (species.disease_susceptibility if species else None) or [],
        }

    async def assemble_water_features(self, plant: Plant) -> dict[str, Any]:
        """Water Recommendation: `species.water_baseline_ml_per_week`, recent `environmental_readings`, and `watering_logs` history (doc §4)."""
        watering_entries, _ = await self._watering.list_for_plant(plant.id, offset=0, limit=_HISTORY_LIMIT)
        env_entries, _ = await self._environmental.list_for_plant(plant.id, offset=0, limit=_HISTORY_LIMIT)
        species = await self._species_for(plant)

        return {
            "plant_id": str(plant.id),
            "species_water_baseline_ml_per_week": species.water_baseline_ml_per_week if species else None,
            "recent_waterings": [
                {
                    "volume_ml": float(w.volume_ml) if w.volume_ml is not None else None,
                    "recorded_at": w.recorded_at.isoformat() if w.recorded_at else None,
                }
                for w in watering_entries
            ],
            "recent_soil_moisture": [
                float(e.soil_moisture_percent) for e in env_entries if e.soil_moisture_percent is not None
            ],
            "recent_temperature": [float(e.temperature_celsius) for e in env_entries if e.temperature_celsius is not None],
        }

    async def assemble_revenue_features(self, nursery_id: uuid.UUID, *, branch_id: uuid.UUID | None = None) -> dict[str, Any]:
        """
        Revenue Forecast: `sales` aggregated by branch/period (doc §4).
        Delegates to the same paginated `SaleRepository.list_for_nursery`
        every other Sales-context reporting method already uses (Module
        9's `SalesReportingService.revenue_report`/`sales_report`) rather
        than re-implementing sale pagination here -- `AIRevenueForecast`'s
        own `predict()` does the seasonality/trend math over the rows this
        returns. `branch_id` is passed through as that method's own
        optional filter kwarg, not a separate query path.
        """
        rows: list[Any] = []
        offset = 0
        page_size = 200
        while True:
            page, total = await self._sales.list_for_nursery(
                nursery_id, offset=offset, limit=page_size, branch_id=branch_id
            )
            rows.extend(page)
            offset += page_size
            if offset >= total or not page:
                break

        daily_totals: dict[str, float] = {}
        for sale in rows:
            if getattr(sale.status, "value", sale.status) == "voided":
                continue
            key = sale.created_at.date().isoformat()
            daily_totals[key] = daily_totals.get(key, 0.0) + float(sale.total_amount)

        return {
            "nursery_id": str(nursery_id),
            "branch_id": str(branch_id) if branch_id else None,
            "daily_revenue": [{"date": d, "revenue": amt} for d, amt in sorted(daily_totals.items())],
            "sale_count": len(rows),
        }


def _days_since(start: datetime | None, end: datetime | None) -> int | None:
    if start is None or end is None:
        return None
    return (end - start).days
