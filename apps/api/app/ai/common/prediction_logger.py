"""
`PredictionLogger` -- the ONE place in this codebase that ever writes an
`AIPrediction` row. FR-8.7's "no AI output without a persisted record"
contract is structural, not a per-module discipline that could be
forgotten: `InferenceBase.run()` (inference_base.py) calls
`PredictionLogger.persist()` itself, in the template method's own body,
so a prediction module's `predict()`/`postprocess()` override has no way
to return a result to its caller without going through this class first.
Mirrors the single-write-path pattern already established by Module 8's
`InventoryService._apply_change()` for `StockMovement` and Module 9's
`SalesOrderService.checkout()` for `Sale`.
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from app.db.enums import AIPredictionType
from app.domain_events import AIPredictionGenerated, AIPredictionGeneratedForBranch, DomainEventPublisher
from app.models.ai import AIPrediction
from app.repositories.interfaces import AIPredictionRepository


class PredictionLogger:
    def __init__(self, *, prediction_repo: AIPredictionRepository, event_publisher: DomainEventPublisher) -> None:
        self._predictions = prediction_repo
        self._events = event_publisher

    async def persist(
        self,
        *,
        prediction_type: AIPredictionType,
        nursery_id: uuid.UUID,
        model_version: str,
        result: dict[str, Any],
        branch_id: uuid.UUID | None = None,
        plant_id: uuid.UUID | None = None,
        confidence: Decimal | None = None,
        explanation: str | None = None,
        inputs_summary: dict[str, Any] | None = None,
        actor_user_id: uuid.UUID | None = None,
        request_id: str | None = None,
        latency_ms: int | None = None,
    ) -> AIPrediction:
        prediction = AIPrediction(
            nursery_id=nursery_id,
            branch_id=branch_id,
            plant_id=plant_id,
            prediction_type=prediction_type,
            model_version=model_version,
            result=result,
            confidence=confidence,
            explanation=explanation,
            inputs_summary=inputs_summary,
            # Added by Phase 6 Module 13 ("AI Administration", inference
            # latency) -- optional, wired from `InferenceBase.run()`'s own
            # wall-clock measurement (see that class's docstring).
            latency_ms=latency_ms,
        )
        prediction = await self._predictions.add(prediction)

        confidence_str = str(confidence) if confidence is not None else None
        if plant_id is not None:
            await self._events.publish(
                AIPredictionGenerated(
                    aggregate_id=plant_id,
                    nursery_id=nursery_id,
                    actor_user_id=actor_user_id,
                    prediction_id=prediction.id,
                    prediction_type=prediction_type.value,
                    model_version=model_version,
                    confidence=confidence_str,
                ),
                request_id=request_id,
            )
        elif branch_id is not None:
            await self._events.publish(
                AIPredictionGeneratedForBranch(
                    aggregate_id=branch_id,
                    nursery_id=nursery_id,
                    actor_user_id=actor_user_id,
                    prediction_id=prediction.id,
                    prediction_type=prediction_type.value,
                    model_version=model_version,
                    confidence=confidence_str,
                ),
                request_id=request_id,
            )
        # Neither plant_id nor branch_id: an org-wide prediction with no
        # single aggregate to attribute the event to. None of the six
        # modules in this version produce one (all are plant- or
        # branch-scoped), so this is a documented no-op, not a gap --
        # the prediction row itself is still always persisted above,
        # satisfying FR-8.7 regardless of whether an event was publishable.

        return prediction
