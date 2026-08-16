"""
Phase 6 Module 10 (AI Platform). Six prediction modules
(`disease_detection`, `growth_prediction`, `survival_prediction`,
`water_recommendation`, `revenue_forecast`, `recommendation_engine`) plus
the AI Assistant (`assistant`), all sharing `app/ai/common/`. Maps to
docs/architecture/06-ai-architecture.md's module table.

Models run in-process within the FastAPI runtime (no separate
model-serving infrastructure) -- see that doc's §2 for the full
reasoning. Nothing in this package touches a route or a repository
directly except through the shared `app/ai/common/` interfaces
(`FeatureStore`, `PredictionLogger`, `ModelRegistry`) and the Protocol
repository interfaces every other module already uses -- these are pure
inference/orchestration classes, unit-testable with the same in-memory
Fake repositories as everything else in this codebase.
"""
