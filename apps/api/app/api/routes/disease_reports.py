"""
Module 6 -- Health & Disease (LLD "Module: Health & Disease"):
`GET/POST /plants/{plant_id}/disease-reports`, `GET /disease-reports`,
`GET /disease-reports/{id}`, `POST /disease-reports/{id}/confirm`,
`POST /disease-reports/{id}/dismiss`, `GET/POST /disease-reports/{id}/treatments`.

`disease:approve` (confirm/dismiss) is a distinct, narrower permission
than `disease:write` (log observation) -- straight from the LLD's own
Health & Disease module description and `docs/ux/07-role-permission-
matrix.md`. Confirming an above-threshold report is also the trigger
that drives a plant into `Under Treatment`
(docs/ux/13-digital-twin-lifecycle.md) -- `DiseaseReportService.
confirm_report` (called from here) already does that internally via
`PlantService.transition_status`, so this route stays thin.
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import (
    PageParams,
    TenantContext,
    get_authorization_service,
    get_current_user,
    get_disease_report_service,
    get_plant_service,
    get_tenant_context,
    get_treatment_service,
    raise_if_denied,
    request_context,
)
from app.core.responses import ErrorResponse, Page, PageMeta
from app.db.enums import DiseaseReportSeverity, DiseaseReportStatus
from app.models.identity import User
from app.models.plants import Plant
from app.schemas.plants import (
    ApplyTreatmentRequest,
    CreateDiseaseReportRequest,
    DismissDiseaseReportRequest,
    DiseaseReportResponse,
    TreatmentResponse,
)
from app.services.authorization_service import AuthorizationService
from app.services.disease_service import DiseaseReportService, TreatmentService
from app.services.plant_service import PlantService

router = APIRouter()

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication failed"},
    403: {"model": ErrorResponse, "description": "Missing permission or cross-tenant/cross-branch access"},
    404: {"model": ErrorResponse, "description": "Disease report not found"},
}


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


async def _authorize_report(
    *, report_id: uuid.UUID, permission: str, request: Request, user: User,
    disease_service: DiseaseReportService, plant_service: PlantService, authz: AuthorizationService,
):
    report = await disease_service.get_report(report_id)
    plant = await plant_service.get_plant(report.plant_id)
    decision = await authz.authorize(
        user=user, permission=permission, resource_type="disease_report", resource_id=report.id,
        target_nursery_id=plant.nursery_id, target_branch_id=plant.branch_id,
        context=request_context(request),
    )
    if not decision.allowed:
        raise raise_if_denied(decision)
    return report


@router.get(
    "/plants/{plant_id}/disease-reports", response_model=list[DiseaseReportResponse], responses=_ERROR_RESPONSES,
    summary="List a plant's disease reports (also its disease history for Health Records)",
)
async def list_disease_reports_for_plant(
    plant_id: uuid.UUID, request: Request, user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service),
    disease_service: DiseaseReportService = Depends(get_disease_report_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> list[DiseaseReportResponse]:
    await _authorize_plant(plant_id=plant_id, permission="disease:read", request=request, user=user, plant_service=plant_service, authz=authz)
    reports = await disease_service.list_for_plant(plant_id)
    return [DiseaseReportResponse.model_validate(r) for r in reports]


@router.post(
    "/plants/{plant_id}/disease-reports", response_model=DiseaseReportResponse, status_code=status.HTTP_201_CREATED,
    responses=_ERROR_RESPONSES, summary="Log a disease report against a plant (draft status)",
)
async def create_disease_report(
    plant_id: uuid.UUID, body: CreateDiseaseReportRequest, request: Request, user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service),
    disease_service: DiseaseReportService = Depends(get_disease_report_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> DiseaseReportResponse:
    await _authorize_plant(plant_id=plant_id, permission="disease:write", request=request, user=user, plant_service=plant_service, authz=authz)
    report = await disease_service.create_report(
        plant_id=plant_id, condition_name=body.condition_name, severity=body.severity, actor_user_id=user.id,
        is_ai_sourced=body.is_ai_sourced, ai_confidence=body.ai_confidence, photo_url=body.photo_url,
        request_id=request_context(request).request_id,
    )
    return DiseaseReportResponse.model_validate(report)


@router.get(
    "/disease-reports", response_model=Page[DiseaseReportResponse], responses={401: _ERROR_RESPONSES[401], 403: _ERROR_RESPONSES[403]},
    summary="List/filter the caller's organization's disease reports",
)
async def list_disease_reports(
    request: Request,
    page_params: PageParams = Depends(),
    status_filter: DiseaseReportStatus | None = None,
    severity: DiseaseReportSeverity | None = None,
    user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
    disease_service: DiseaseReportService = Depends(get_disease_report_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> Page[DiseaseReportResponse]:
    if tenant.org_id is None:
        return Page(items=[], meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=0, total_pages=0))
    decision = await authz.authorize(
        user=user, permission="disease:read", resource_type="disease_report",
        target_nursery_id=tenant.org_id, context=request_context(request),
    )
    if not decision.allowed:
        raise raise_if_denied(decision)

    rows, total = await disease_service.list_for_nursery(
        nursery_id=tenant.org_id, offset=page_params.offset, limit=page_params.page_size,
        status=status_filter, severity=severity,
    )
    total_pages = (total + page_params.page_size - 1) // page_params.page_size if total else 0
    return Page(
        items=[DiseaseReportResponse.model_validate(r) for r in rows],
        meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=total, total_pages=total_pages),
    )


@router.get("/disease-reports/{id}", response_model=DiseaseReportResponse, responses=_ERROR_RESPONSES, summary="Get a disease report by id")
async def get_disease_report(
    id: uuid.UUID, request: Request, user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service),
    disease_service: DiseaseReportService = Depends(get_disease_report_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> DiseaseReportResponse:
    report = await _authorize_report(
        report_id=id, permission="disease:read", request=request, user=user,
        disease_service=disease_service, plant_service=plant_service, authz=authz,
    )
    return DiseaseReportResponse.model_validate(report)


@router.post(
    "/disease-reports/{id}/confirm", response_model=DiseaseReportResponse,
    responses={**_ERROR_RESPONSES, 409: {"model": ErrorResponse, "description": "Report is not a draft"}},
    summary="Confirm a draft disease report (requires disease:approve; may auto-transition the plant to Under Treatment)",
)
async def confirm_disease_report(
    id: uuid.UUID, request: Request, user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service),
    disease_service: DiseaseReportService = Depends(get_disease_report_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> DiseaseReportResponse:
    await _authorize_report(
        report_id=id, permission="disease:approve", request=request, user=user,
        disease_service=disease_service, plant_service=plant_service, authz=authz,
    )
    report = await disease_service.confirm_report(report_id=id, actor_user_id=user.id, request_id=request_context(request).request_id)
    return DiseaseReportResponse.model_validate(report)


@router.post(
    "/disease-reports/{id}/dismiss", response_model=DiseaseReportResponse,
    responses={**_ERROR_RESPONSES, 409: {"model": ErrorResponse, "description": "Report is not a draft"}},
    summary="Dismiss a draft disease report (requires disease:approve)",
)
async def dismiss_disease_report(
    id: uuid.UUID, body: DismissDiseaseReportRequest, request: Request, user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service),
    disease_service: DiseaseReportService = Depends(get_disease_report_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> DiseaseReportResponse:
    await _authorize_report(
        report_id=id, permission="disease:approve", request=request, user=user,
        disease_service=disease_service, plant_service=plant_service, authz=authz,
    )
    report = await disease_service.dismiss_report(
        report_id=id, actor_user_id=user.id, dismissed_reason=body.dismissed_reason,
        request_id=request_context(request).request_id,
    )
    return DiseaseReportResponse.model_validate(report)


@router.get(
    "/disease-reports/{id}/treatments", response_model=list[TreatmentResponse], responses=_ERROR_RESPONSES,
    summary="List treatments applied against a disease report (also feeds Health Records' treatment history)",
)
async def list_treatments(
    id: uuid.UUID, request: Request, user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service),
    disease_service: DiseaseReportService = Depends(get_disease_report_service),
    treatment_service: TreatmentService = Depends(get_treatment_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> list[TreatmentResponse]:
    await _authorize_report(
        report_id=id, permission="disease:read", request=request, user=user,
        disease_service=disease_service, plant_service=plant_service, authz=authz,
    )
    treatments = await treatment_service.list_for_report(id)
    return [TreatmentResponse.model_validate(t) for t in treatments]


@router.post(
    "/disease-reports/{id}/treatments", response_model=TreatmentResponse, status_code=status.HTTP_201_CREATED,
    responses={**_ERROR_RESPONSES, 409: {"model": ErrorResponse, "description": "Report already resolved"}},
    summary="Apply a treatment (an outcome of Recovered/Plant lost closes the report and transitions the plant)",
)
async def apply_treatment(
    id: uuid.UUID, body: ApplyTreatmentRequest, request: Request, user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service),
    disease_service: DiseaseReportService = Depends(get_disease_report_service),
    treatment_service: TreatmentService = Depends(get_treatment_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> TreatmentResponse:
    await _authorize_report(
        report_id=id, permission="disease:write", request=request, user=user,
        disease_service=disease_service, plant_service=plant_service, authz=authz,
    )
    treatment = await treatment_service.apply_treatment(
        disease_report_id=id, description=body.description, outcome=body.outcome, actor_user_id=user.id,
        request_id=request_context(request).request_id,
    )
    return TreatmentResponse.model_validate(treatment)
