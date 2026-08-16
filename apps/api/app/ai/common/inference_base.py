"""
`InferenceBase` -- the template method every one of the six prediction
modules implements, per docs/architecture/06-ai-architecture.md §3
(Inference Pipeline):

    FeatureStore.assemble -> preprocess -> predict -> postprocess
        -> PredictionLogger.persist (ALWAYS, before return) -> return

`run()` (defined here, final, not overridable) owns the last two steps
itself -- a subclass implements `preprocess`/`predict`/`postprocess` and
has no way to hand a result back to its caller without `run()` having
already called `PredictionLogger.persist()` first. This is what makes
FR-8.7 ("no AI output without a persisted record") structural rather than
a per-module discipline: see this package's own `__init__.py` docstring
and `prediction_logger.py`'s.
"""
from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any, ClassVar

from app.ai.common.prediction_logger import PredictionLogger
from app.core.logging import get_logger
from app.db.enums import AIPredictionType
from app.models.ai import AIInferenceFailure, AIPrediction
from app.repositories.interfaces import AIInferenceFailureRepository

logger = get_logger(__name__)


class InferenceBase(ABC):
    """
    `prediction_type`/`capability` are `ClassVar`s (fixed per subclass,
    like every domain event's `event_type`/`aggregate_type` in this
    codebase) -- `capability` is the string `ModelRegistry.get()` looks
    artifacts up by; not every subclass calls `ModelRegistry` (see each
    module's own docstring for which ones do and why), but the name is
    declared uniformly so `docs/architecture/06-ai-architecture.md §1`'s
    module-to-package mapping stays one-to-one and machine-checkable.
    """

    prediction_type: ClassVar[AIPredictionType]
    capability: ClassVar[str]

    def __init__(
        self,
        *,
        prediction_logger: PredictionLogger,
        failure_repo: AIInferenceFailureRepository | None = None,
    ) -> None:
        self._logger = prediction_logger
        # Added by Phase 6 Module 13 ("AI Administration", "AI failures").
        # Optional and defaulted to `None` specifically so this remains a
        # non-breaking, additive change: every one of the six prediction
        # modules built in Module 10 already calls
        # `super().__init__(prediction_logger=prediction_logger)` with no
        # other keyword, and four of them (growth/survival/water/revenue)
        # never override `__init__` at all -- they inherit this one
        # directly. Only `DiseaseDetectionInference.__init__` needed a
        # matching parameter added to forward it through; the other four
        # picked it up automatically, requiring zero changes to
        # already-shipped Module 10 files beyond that one.
        self._failure_repo = failure_repo

    async def run(
        self,
        *,
        nursery_id: uuid.UUID,
        features: dict[str, Any],
        branch_id: uuid.UUID | None = None,
        plant_id: uuid.UUID | None = None,
        actor_user_id: uuid.UUID | None = None,
        request_id: str | None = None,
    ) -> AIPrediction:
        started_at = time.monotonic()
        try:
            preprocessed = await self.preprocess(features)
            model_version, raw_result = await self.predict(preprocessed)
            confidence, explanation, result = await self.postprocess(raw_result)
        except Exception as exc:
            latency_ms = int((time.monotonic() - started_at) * 1000)
            await self._record_failure(
                nursery_id=nursery_id, branch_id=branch_id, latency_ms=latency_ms, error=exc
            )
            raise
        latency_ms = int((time.monotonic() - started_at) * 1000)
        return await self._logger.persist(
            prediction_type=self.prediction_type,
            nursery_id=nursery_id,
            branch_id=branch_id,
            plant_id=plant_id,
            model_version=model_version,
            result=result,
            confidence=confidence,
            explanation=explanation,
            inputs_summary=self.summarize_inputs(features),
            actor_user_id=actor_user_id,
            request_id=request_id,
            latency_ms=latency_ms,
        )

    async def _record_failure(
        self, *, nursery_id: uuid.UUID, branch_id: uuid.UUID | None, latency_ms: int, error: Exception
    ) -> None:
        """
        Best-effort: a failure while *logging* a failure must never mask
        the original exception every one of the six modules' typed-error-
        to-graceful-degradation callers is waiting to catch (FR-3.3). If
        no `failure_repo` was wired in (still true for any deployment that
        constructs an `InferenceBase` subclass without Module 13's
        dependency), this is a silent no-op -- the exception still
        propagates unchanged either way.
        """
        if self._failure_repo is None:
            return
        try:
            await self._failure_repo.add(
                AIInferenceFailure(
                    nursery_id=nursery_id,
                    branch_id=branch_id,
                    capability=self.capability,
                    prediction_type=self.prediction_type.value,
                    error_type=type(error).__name__,
                    error_message=str(error)[:2000],
                    latency_ms=latency_ms,
                )
            )
        except Exception as logging_error:  # noqa: BLE001 -- deliberately broad: never let failure-logging itself raise
            logger.warning("ai_inference_failure_logging_failed", error=str(logging_error))

    @abstractmethod
    async def preprocess(self, features: dict[str, Any]) -> dict[str, Any]:
        """Module-specific: shape `FeatureStore`'s raw assembly into whatever `predict()` needs."""
        ...

    @abstractmethod
    async def predict(self, preprocessed: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Returns `(model_version, raw_result)`. `raw_result` is this module's own internal shape -- `postprocess` turns it into the persisted `result` dict."""
        ...

    @abstractmethod
    async def postprocess(self, raw_result: dict[str, Any]) -> tuple[Decimal | None, str | None, dict[str, Any]]:
        """Returns `(confidence, explanation, result)` -- the exact three fields `ai_predictions.confidence`/`explanation`/`result` persist as."""
        ...

    def summarize_inputs(self, features: dict[str, Any]) -> dict[str, Any]:
        """
        Default: persist the full assembled feature dict as-is. A
        subclass overrides this only if its raw features are large enough
        to warrant a smaller stored summary (none of the six modules in
        this version need to -- `_HISTORY_LIMIT` in feature_store.py
        already bounds every list to a small recent window).
        """
        return features
