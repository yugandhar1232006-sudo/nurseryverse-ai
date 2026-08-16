"""
Module 10 -- AI Predictions (LLD "Module: AI Predictions (orchestration
layer)"): `POST /ai/disease-detection/scan`, `GET /plants/{id}/ai-predictions`,
`GET /ai/predictions/survival-risk`, `GET /ai/predictions/revenue-forecast`,
`GET /ai/recommendations`.

Each prediction endpoint calls its `InferenceBase` subclass's `run()`
directly rather than through a separate "PredictionOrchestrator" class --
the LLD names one as an internal component, but since `InferenceBase.run()`
already enforces the persist-before-return contract structurally (FR-8.7;
see app/ai/common/inference_base.py's own docstring) and each endpoint here
already knows exactly which prediction type it wants, a dispatch-by-string
orchestrator would only add indirection with no behavioral difference --
disclosed as a scoping decision in the Module 10 completion report, not a
silent deviation.

`POST /ai/recommendations/refresh` is not in the LLD's literal "Public
interfaces" list (which shows only the GET) -- it exists because Module
10's own `app/ai/recommendation_engine/engine.py` (already-implemented,
already-tested) explicitly documents an on-demand refresh trigger as its
second of two call sites (the other being a not-yet-built scheduled job),
matching docs/architecture/06-ai-architecture.md §6's "on-demand modules...
go through the same service methods as their triggered counterparts."
Without this endpoint, `ai_recommendations` could only ever be populated by
a Celery Beat job this codebase does not yet have (no Celery worker
infrastructure exists in any module through Module 9) -- leaving the
already-built Recommendation Engine permanently unreachable. Disclosed
explicitly in the Module 10 completion report.
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request, status

from app.ai.disease_detection.inference import DiseaseDetectionInference
from app.ai.growth_prediction.inference import GrowthPredictionInference
from app.ai.recommendation_engine.engine import RecommendationEngine
from app.ai.revenue_forecast.inference import RevenueForecastInference
from app.ai.survival_prediction.inference import SurvivalPredictionInference
from app.ai.water_recommendation.inference import WaterRecommendationInference
from app.api.deps import (
    PageParams,
    TenantContext,
    get_ai_prediction_repository,
    get_ai_recommendation_repository,
    get_authorization_service,
    get_current_user,
    get_disease_detection_inference,
    get_feature_store,
    get_growth_prediction_inference,
    get_plant_service,
    get_recommendation_engine,
    get_revenue_forecast_inference,
    get_survival_prediction_inference,
    get_tenant_context,
    get_water_recommendation_inference,
    raise_if_denied,
    request_context,
)
from app.ai.common.feature_store import FeatureStore
from app.core.exceptions import PermissionDeniedError
from app.core.responses import ErrorResponse, Page, PageMeta
from app.db.enums import AIPredictionType, AIRecommendationStatus
from app.models.identity import User
from app.models.plants import Plant
from app.repositories.interfaces import AIPredictionRepository, AIRecommendationRepository
from app.schemas.ai import AIPredictionResponse, AIRecommendationResponse, RunDiseaseDetectionRequest
from app.services.authorization_service import AuthorizationService
from app.services.plant_service import PlantService

router = APIRouter()

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication failed"},
    403: {"model": ErrorResponse, "description": "Missing permission or cross-tenant/cross-branch access"},
    404: {"model": ErrorResponse, "description": "Plant not found"},
    503: {"model": ErrorResponse, "description": "The requested AI capability has no trained model artifact configured"},
}


def _page(items: list[Any], *, page_params: PageParams, total: int) -> Page[Any]:
    total_pages = (total + page_params.page_size - 1) // page_params.page_size if total else 0
    return Page(
        items=items,
        meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=total, total_pages=total_pages),
    )


async def _authorize_plant(
    *, plant_id: uuid.UUID, permission: str, request: Request, user: User,
    plant_service: PlantService, authz: AuthorizationService,
) -> Plant:
    plant = await plant_service.get_plant(plant_id)
    decision = await authz.authorize(
        user=user, permission=permission, resource_type="plant", resource_id=plant.id,
        target_nursery_id=plant.nursery_id, target_branch_id=plant.branch_id,
        context=request_context(request),
    )
    if not decision.allowed:
        raise raise_if_denied(decision)
    return plant


async def _authorize_org_scope(
    *, permission: str, resource_type: str, request: Request, user: User,
    tenant: TenantContext, branch_id: uuid.UUID | None, authz: AuthorizationService,
) -> uuid.UUID | None:
    """
    Shared by every `/ai/predictions/*`, `/ai/recommendations` org-wide
    endpoint below -- mirrors `disease_reports.list_disease_reports`'s
    org-wide-list authorization pattern exactly, INCLUDING that pattern's
    "no org yet" handling: `tenant.org_id is None` returns `None` (not an
    error) so the caller can hand back its own empty response (a user with
    no `RoleAssignment` yet isn't a permission failure, it's "nothing to
    show" -- see `TenantContext`'s own docstring on why "no org" and "any
    org" are deliberately never conflated).
    """
    if tenant.org_id is None:
        return None
    decision = await authz.authorize(
        user=user, permission=permission, resource_type=resource_type,
        target_nursery_id=tenant.org_id, target_branch_id=branch_id, context=request_context(request),
    )
    if not decision.allowed:
        raise raise_if_denied(decision)
    return tenant.org_id


# ==============================================================================
# Disease Detection (FR-8.1)
# ==============================================================================


@router.post(
    "/ai/disease-detection/scan", response_model=AIPredictionResponse, status_code=status.HTTP_201_CREATED,
    responses=_ERROR_RESPONSES,
    summary="Run AI Disease Detection against a plant photo (FR-8.1; always persists an ai_predictions row before returning, per FR-8.7)",
)
async def run_disease_detection(
    body: RunDiseaseDetectionRequest, request: Request, user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service),
    inference: DiseaseDetectionInference = Depends(get_disease_detection_inference),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> AIPredictionResponse:
    plant = await _authorize_plant(
        plant_id=body.plant_id, permission="ai_predictions:run", request=request, user=user,
        plant_service=plant_service, authz=authz,
    )
    prediction = await inference.run(
        nursery_id=plant.nursery_id, branch_id=plant.branch_id, plant_id=plant.id,
        features={"image_url": body.image_url}, actor_user_id=user.id,
        request_id=request_context(request).request_id,
    )
    return AIPredictionResponse.model_validate(prediction)


# ==============================================================================
# Historical predictions (FR-8.8)
# ==============================================================================


@router.get(
    "/plants/{plant_id}/ai-predictions", response_model=Page[AIPredictionResponse], responses=_ERROR_RESPONSES,
    summary="Historical AI predictions for a plant, newest first (FR-8.8)",
)
async def list_plant_ai_predictions(
    plant_id: uuid.UUID, request: Request, page_params: PageParams = Depends(),
    prediction_type: AIPredictionType | None = None, user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service),
    prediction_repo: AIPredictionRepository = Depends(get_ai_prediction_repository),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> Page[AIPredictionResponse]:
    await _authorize_plant(
        plant_id=plant_id, permission="ai_predictions:read", request=request, user=user,
        plant_service=plant_service, authz=authz,
    )
    rows, total = await prediction_repo.list_for_plant(
        plant_id, prediction_type=prediction_type, offset=page_params.offset, limit=page_params.page_size
    )
    return _page([AIPredictionResponse.model_validate(r) for r in rows], page_params=page_params, total=total)


# ==============================================================================
# Growth / Survival / Water Recommendation -- run on-demand for a specific plant
# ==============================================================================


async def _run_plant_prediction(
    *, plant_id: uuid.UUID, request: Request, user: User, plant_service: PlantService,
    feature_store: FeatureStore, authz: AuthorizationService,
    assemble: Any, inference: Any,
) -> AIPredictionResponse:
    plant = await _authorize_plant(
        plant_id=plant_id, permission="ai_predictions:run", request=request, user=user,
        plant_service=plant_service, authz=authz,
    )
    features = await assemble(plant)
    prediction = await inference.run(
        nursery_id=plant.nursery_id, branch_id=plant.branch_id, plant_id=plant.id, features=features,
        actor_user_id=user.id, request_id=request_context(request).request_id,
    )
    return AIPredictionResponse.model_validate(prediction)


@router.post(
    "/plants/{plant_id}/ai-predictions/growth", response_model=AIPredictionResponse, status_code=status.HTTP_201_CREATED,
    responses=_ERROR_RESPONSES, summary="Run AI Growth Prediction for a plant on demand (FR-8.2)",
)
async def run_growth_prediction(
    plant_id: uuid.UUID, request: Request, user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service),
    feature_store: FeatureStore = Depends(get_feature_store),
    inference: GrowthPredictionInference = Depends(get_growth_prediction_inference),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> AIPredictionResponse:
    return await _run_plant_prediction(
        plant_id=plant_id, request=request, user=user, plant_service=plant_service, feature_store=feature_store,
        authz=authz, assemble=feature_store.assemble_growth_features, inference=inference,
    )


@router.post(
    "/plants/{plant_id}/ai-predictions/survival", response_model=AIPredictionResponse, status_code=status.HTTP_201_CREATED,
    responses=_ERROR_RESPONSES, summary="Run AI Survival Prediction for a plant on demand (FR-8.3)",
)
async def run_survival_prediction(
    plant_id: uuid.UUID, request: Request, user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service),
    feature_store: FeatureStore = Depends(get_feature_store),
    inference: SurvivalPredictionInference = Depends(get_survival_prediction_inference),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> AIPredictionResponse:
    return await _run_plant_prediction(
        plant_id=plant_id, request=request, user=user, plant_service=plant_service, feature_store=feature_store,
        authz=authz, assemble=feature_store.assemble_survival_features, inference=inference,
    )


@router.post(
    "/plants/{plant_id}/ai-predictions/water", response_model=AIPredictionResponse, status_code=status.HTTP_201_CREATED,
    responses=_ERROR_RESPONSES, summary="Run AI Water Recommendation for a plant on demand (FR-8.4)",
)
async def run_water_recommendation(
    plant_id: uuid.UUID, request: Request, user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service),
    feature_store: FeatureStore = Depends(get_feature_store),
    inference: WaterRecommendationInference = Depends(get_water_recommendation_inference),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> AIPredictionResponse:
    return await _run_plant_prediction(
        plant_id=plant_id, request=request, user=user, plant_service=plant_service, feature_store=feature_store,
        authz=authz, assemble=feature_store.assemble_water_features, inference=inference,
    )


# ==============================================================================
# Survival Risk (org/branch-wide view) (FR-8.3)
# ==============================================================================


@router.get(
    "/ai/predictions/survival-risk", response_model=Page[AIPredictionResponse],
    responses={401: _ERROR_RESPONSES[401], 403: _ERROR_RESPONSES[403]},
    summary="Survival Prediction history across the caller's org (optionally filtered to one branch), newest first",
)
async def list_survival_risk(
    request: Request, page_params: PageParams = Depends(), branch_id: uuid.UUID | None = None,
    user: User = Depends(get_current_user), tenant: TenantContext = Depends(get_tenant_context),
    prediction_repo: AIPredictionRepository = Depends(get_ai_prediction_repository),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> Page[AIPredictionResponse]:
    org_id = await _authorize_org_scope(
        permission="ai_predictions:read", resource_type="ai_prediction", request=request, user=user,
        tenant=tenant, branch_id=branch_id, authz=authz,
    )
    if org_id is None:
        return _page([], page_params=page_params, total=0)
    if branch_id is not None:
        rows, total = await prediction_repo.list_for_branch(
            branch_id, prediction_type=AIPredictionType.SURVIVAL_PREDICTION,
            offset=page_params.offset, limit=page_params.page_size,
        )
    else:
        rows, total = await prediction_repo.list_for_nursery(
            org_id, prediction_type=AIPredictionType.SURVIVAL_PREDICTION,
            offset=page_params.offset, limit=page_params.page_size,
        )
    return _page([AIPredictionResponse.model_validate(r) for r in rows], page_params=page_params, total=total)


# ==============================================================================
# Revenue Forecast (org/branch-wide) (FR-8.5)
# ==============================================================================


@router.post(
    "/ai/predictions/revenue-forecast", response_model=AIPredictionResponse, status_code=status.HTTP_201_CREATED,
    responses={401: _ERROR_RESPONSES[401], 403: _ERROR_RESPONSES[403]},
    summary="Run AI Revenue Forecast for the caller's org (optionally one branch) on demand (FR-8.5)",
)
async def run_revenue_forecast(
    request: Request, branch_id: uuid.UUID | None = None, user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context), feature_store: FeatureStore = Depends(get_feature_store),
    inference: RevenueForecastInference = Depends(get_revenue_forecast_inference),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> AIPredictionResponse:
    org_id = await _authorize_org_scope(
        permission="ai_predictions:run", resource_type="ai_prediction", request=request, user=user,
        tenant=tenant, branch_id=branch_id, authz=authz,
    )
    if org_id is None:
        raise PermissionDeniedError("The user has no organization membership to authorize against.")
    features = await feature_store.assemble_revenue_features(org_id, branch_id=branch_id)
    prediction = await inference.run(
        nursery_id=org_id, branch_id=branch_id, features=features, actor_user_id=user.id,
        request_id=request_context(request).request_id,
    )
    return AIPredictionResponse.model_validate(prediction)


@router.get(
    "/ai/predictions/revenue-forecast", response_model=Page[AIPredictionResponse],
    responses={401: _ERROR_RESPONSES[401], 403: _ERROR_RESPONSES[403]},
    summary="Revenue Forecast history for the caller's org (optionally one branch), newest first",
)
async def list_revenue_forecasts(
    request: Request, page_params: PageParams = Depends(), branch_id: uuid.UUID | None = None,
    user: User = Depends(get_current_user), tenant: TenantContext = Depends(get_tenant_context),
    prediction_repo: AIPredictionRepository = Depends(get_ai_prediction_repository),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> Page[AIPredictionResponse]:
    org_id = await _authorize_org_scope(
        permission="ai_predictions:read", resource_type="ai_prediction", request=request, user=user,
        tenant=tenant, branch_id=branch_id, authz=authz,
    )
    if org_id is None:
        return _page([], page_params=page_params, total=0)
    if branch_id is not None:
        rows, total = await prediction_repo.list_for_branch(
            branch_id, prediction_type=AIPredictionType.REVENUE_FORECAST,
            offset=page_params.offset, limit=page_params.page_size,
        )
    else:
        rows, total = await prediction_repo.list_for_nursery(
            org_id, prediction_type=AIPredictionType.REVENUE_FORECAST,
            offset=page_params.offset, limit=page_params.page_size,
        )
    return _page([AIPredictionResponse.model_validate(r) for r in rows], page_params=page_params, total=total)


# ==============================================================================
# Recommendation Engine (FR-8.6)
# ==============================================================================


@router.get(
    "/ai/recommendations", response_model=Page[AIRecommendationResponse],
    responses={401: _ERROR_RESPONSES[401], 403: _ERROR_RESPONSES[403]},
    summary="List AI recommendations for the caller's org (optionally filtered to one branch/status)",
)
async def list_recommendations(
    request: Request, page_params: PageParams = Depends(), branch_id: uuid.UUID | None = None,
    status_filter: AIRecommendationStatus | None = None,
    user: User = Depends(get_current_user), tenant: TenantContext = Depends(get_tenant_context),
    recommendation_repo: AIRecommendationRepository = Depends(get_ai_recommendation_repository),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> Page[AIRecommendationResponse]:
    org_id = await _authorize_org_scope(
        permission="ai_predictions:read", resource_type="ai_recommendation", request=request, user=user,
        tenant=tenant, branch_id=branch_id, authz=authz,
    )
    if org_id is None:
        return _page([], page_params=page_params, total=0)
    if branch_id is not None:
        rows, total = await recommendation_repo.list_for_branch(
            branch_id, status=status_filter, offset=page_params.offset, limit=page_params.page_size
        )
    else:
        rows, total = await recommendation_repo.list_for_nursery(
            org_id, status=status_filter, offset=page_params.offset, limit=page_params.page_size
        )
    return _page([AIRecommendationResponse.model_validate(r) for r in rows], page_params=page_params, total=total)


@router.post(
    "/ai/recommendations/refresh", response_model=list[AIRecommendationResponse], status_code=status.HTTP_201_CREATED,
    responses={401: _ERROR_RESPONSES[401], 403: _ERROR_RESPONSES[403]},
    summary="On-demand recommendation refresh for one branch, from that branch's latest Survival Predictions (see module docstring on why this endpoint exists)",
)
async def refresh_recommendations(
    branch_id: uuid.UUID, request: Request, user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
    prediction_repo: AIPredictionRepository = Depends(get_ai_prediction_repository),
    recommendation_repo: AIRecommendationRepository = Depends(get_ai_recommendation_repository),
    engine: RecommendationEngine = Depends(get_recommendation_engine),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> list[AIRecommendationResponse]:
    org_id = await _authorize_org_scope(
        permission="ai_predictions:run", resource_type="ai_recommendation", request=request, user=user,
        tenant=tenant, branch_id=branch_id, authz=authz,
    )
    if org_id is None:
        raise PermissionDeniedError("The user has no organization membership to authorize against.")
    # `list_for_branch` returns newest-first (this repository's established convention -- see
    # AIPredictionRepository.list_for_plant's own docstring); de-duplicating by `plant_id` keeping only the
    # first occurrence per plant therefore keeps each plant's MOST RECENT Survival Prediction, matching
    # `RecommendationEngine.generate_survival_risk_recommendations`'s own documented caller contract ("the
    # latest Survival Prediction row per plant -- the caller is responsible for that de-duplication").
    rows, _ = await prediction_repo.list_for_branch(
        branch_id, prediction_type=AIPredictionType.SURVIVAL_PREDICTION, offset=0, limit=500
    )
    latest_by_plant: dict[uuid.UUID, Any] = {}
    for row in rows:
        if row.plant_id is not None and row.plant_id not in latest_by_plant:
            latest_by_plant[row.plant_id] = row

    recommendations = engine.generate_survival_risk_recommendations(
        nursery_id=org_id, branch_id=branch_id, predictions=list(latest_by_plant.values())
    )
    persisted = [await recommendation_repo.add(r) for r in recommendations]
    return [AIRecommendationResponse.model_validate(r) for r in persisted]
