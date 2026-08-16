"""
Shared AI infrastructure every one of the six prediction modules builds
on -- docs/architecture/06-ai-architecture.md §1's "All seven share
`app/ai/common/`" line.
"""
from app.ai.common.feature_store import FeatureStore  # noqa: F401
from app.ai.common.inference_base import InferenceBase  # noqa: F401
from app.ai.common.model_registry import ModelRegistry  # noqa: F401
from app.ai.common.prediction_logger import PredictionLogger  # noqa: F401

__all__ = ["FeatureStore", "InferenceBase", "ModelRegistry", "PredictionLogger"]
