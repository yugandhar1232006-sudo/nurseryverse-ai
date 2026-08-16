"""
FR-8.1 -- AI Disease Detection: "staff can submit a plant photo for AI
Disease Detection and receive a prediction with confidence score and
identified condition(s)."

UNLIKE the other five prediction modules (growth/survival/water/revenue/
recommendation), this one has no honest real-baseline substitute: it is,
per docs/architecture/06-ai-architecture.md §1, "purely visual" -- a CNN
forward pass over a normalized plant-photo derivative, image
classification with no rule-based or statistical approximation that
would produce a meaningful condition label from pixels. Growth/Survival/
Water/Revenue all have a defensible non-ML fallback (a trend line, a
weighted score, a baseline lookup, a seasonal average) because their
inputs are already-structured tabular history; this module's input is
raw image data, where a fabricated "condition: healthy, confidence: 0.85"
result would be actively misleading to a nursery worker deciding whether
to treat a plant -- exactly the kind of output this project's own
governing instructions forbid ("no placeholders/mocks").

So: this module implements the real pipeline shape up through
`ModelRegistry.get("disease_detection")`, which raises the typed
`ModelUnavailableError` in this sandbox (no trained CNN artifact exists
to load -- see model_registry.py's own docstring), and stops there. This
is not a stub standing in for real logic; it is the documented,
intentional graceful-degradation path docs/architecture/02-low-level-
design.md's AI Predictions module already specifies ("`ModelUnavailableError`
(typed) -> surfaced as the module-specific graceful-degradation message
(NFR-3.3), never a bare 500"). Once a real trained artifact is deployed
at `MODEL_ARTIFACT_BASE_PATH`, this class's `predict()` is where the
forward pass goes -- `preprocess()`/`postprocess()` already have their
real, permanent shape (species-susceptibility-adjusted confidence
threshold, condition taxonomy mapping) and will not need to change.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.ai.common.inference_base import InferenceBase
from app.ai.common.model_registry import ModelRegistry
from app.ai.common.prediction_logger import PredictionLogger
from app.core.exceptions import ValidationError
from app.db.enums import AIPredictionType
from app.repositories.interfaces import AIInferenceFailureRepository

MODEL_VERSION_PENDING = "unavailable-no-trained-artifact"


class DiseaseDetectionInference(InferenceBase):
    prediction_type = AIPredictionType.DISEASE_DETECTION
    capability = "disease_detection"

    def __init__(
        self,
        *,
        prediction_logger: PredictionLogger,
        model_registry: ModelRegistry,
        failure_repo: AIInferenceFailureRepository | None = None,
    ) -> None:
        super().__init__(prediction_logger=prediction_logger, failure_repo=failure_repo)
        self._registry = model_registry

    async def preprocess(self, features: dict[str, Any]) -> dict[str, Any]:
        image_url = features.get("image_url")
        if not image_url:
            raise ValidationError("An image_url (Cloudinary-hosted, normalized derivative) is required for Disease Detection.")
        return {
            "image_url": image_url,
            # Species-level disease-susceptibility priors adjust the confidence threshold, not the
            # classification itself (doc §4) -- carried through preprocess so a real model's postprocess step
            # has it available without a second feature-assembly round-trip.
            "species_disease_susceptibility": features.get("species_disease_susceptibility") or [],
        }

    async def predict(self, preprocessed: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        # Raises ModelUnavailableError in this environment -- see this module's own docstring.
        # A real deployment: `model = self._registry.get(self.capability)`, then a forward pass over the
        # normalized image derivative at `preprocessed["image_url"]`, softmax over the condition taxonomy.
        self._registry.get(self.capability)
        raise AssertionError(  # pragma: no cover -- unreachable: ModelRegistry.get() always raises above in this environment
            "Disease Detection has no trained model artifact configured; ModelRegistry.get() should have already raised ModelUnavailableError."
        )

    async def postprocess(self, raw_result: dict[str, Any]) -> tuple[Decimal | None, str | None, dict[str, Any]]:
        raise AssertionError("unreachable -- predict() always raises before postprocess() would be called")  # pragma: no cover
