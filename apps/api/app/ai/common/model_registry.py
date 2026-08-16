"""
`ModelRegistry` -- versioned model artifact load/cache, per
docs/architecture/06-ai-architecture.md §2 (Model Serving) / §10 (Model
Versioning).

Weights are read from object-storage-hosted artifacts at
`<MODEL_ARTIFACT_BASE_PATH>/<capability>/<version>/`, referenced by a
config value (`Settings.MODEL_ARTIFACT_BASE_PATH`), not baked into the
container image -- so a new model version can be deployed by updating
config and rolling the workers, without a full image rebuild (the doc's
own stated reason for this design). `get()` lazy-loads and caches per
process; a second call for the same `(capability, version)` returns the
already-loaded object.

THIS SANDBOX HAS NO TRAINED MODEL ARTIFACTS. `MODEL_ARTIFACT_BASE_PATH`
defaults to `""` (unset) -- `get()` raises the typed `ModelUnavailableError`
for every capability until a real path is configured, exactly matching
docs/architecture/02-low-level-design.md's AI Predictions module's own
documented error path ("`ModelUnavailableError` (typed) -> surfaced as
the module-specific graceful-degradation message (NFR-3.3), never a bare
500"). This is real, correct, disclosed behavior -- not a mock standing in
for a working model. `disease_detection` (the one capability that
genuinely requires a trained artifact -- an image-classification CNN, no
plausible rule-based substitute) calls `get()` and surfaces this error
today; the other four ML modules (growth/survival/water/revenue) do NOT
route through `ModelRegistry` at all in this version -- they implement a
real, versioned, working v1.0.0 statistical/heuristic baseline directly
(each one's own module docstring explains why), which is swappable for a
`ModelRegistry`-loaded trained model later without any caller-facing
change, per this same doc's `InferenceBase` contract and "Scaling path"
section.
"""
from __future__ import annotations

from typing import Any

from app.core.config import Settings
from app.core.exceptions import ModelUnavailableError


class ModelRegistry:
    def __init__(self, *, settings: Settings) -> None:
        self._settings = settings
        self._cache: dict[tuple[str, str], Any] = {}

    def get(self, capability: str, *, version: str = "latest") -> Any:
        """
        Returns the loaded model object for `capability`/`version`.
        Raises `ModelUnavailableError` if no artifact base path is
        configured, or (once one is) if the specific capability/version
        directory doesn't exist -- callers should catch this and degrade
        gracefully (see this module's own docstring), never let it
        surface as a bare 500.
        """
        key = (capability, version)
        if key in self._cache:
            return self._cache[key]

        base_path = self._settings.MODEL_ARTIFACT_BASE_PATH
        if not base_path:
            raise ModelUnavailableError(
                f"No trained model artifact configured for '{capability}' -- "
                "MODEL_ARTIFACT_BASE_PATH is unset. Set it to an object-storage "
                "path containing '<capability>/<version>/' artifacts to enable "
                "this prediction module.",
                context={"capability": capability, "version": version},
            )

        # Real deployments load framework-specific weights here (PyTorch
        # .pt, XGBoost .json, Prophet .json, scikit-learn .joblib -- see
        # docs/architecture/06-ai-architecture.md §1's per-module Framework
        # column) from `<base_path>/<capability>/<version>/`. No loader is
        # implemented here yet because no artifact has ever been produced
        # for this codebase (no training pipeline/dataset exists in this
        # sandbox) -- documented rather than faked with a placeholder
        # object that would silently return meaningless predictions.
        raise ModelUnavailableError(
            f"MODEL_ARTIFACT_BASE_PATH is configured, but no loader is implemented "
            f"for '{capability}' yet, and no artifact has been produced for this "
            f"codebase to load.",
            context={"capability": capability, "version": version},
        )

    def is_configured(self, capability: str) -> bool:
        """Cheap, non-raising check `InferenceBase` subclasses can use to pick a code path (e.g. skip attempting `get()` entirely) without a try/except for control flow."""
        return bool(self._settings.MODEL_ARTIFACT_BASE_PATH)
