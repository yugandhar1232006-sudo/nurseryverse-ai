"""
Module 6 -- Health & Disease (LLD "Module: Health & Disease"): DiseaseReport
lifecycle (draft -> confirmed/dismissed -> treated -> resolved) and
Treatment tracking. Depends on `PlantService` (one direction only --
`PlantService` itself only depends on the read-only `DiseaseReportRepository`/
`TreatmentRepository` for its own status-transition guards, never on these
two service classes, so there's no import cycle) to actually drive the
`PlantStatus` state machine at the two points the lifecycle doc says a
disease/treatment event *is* the trigger:
"Disease Report confirmed (severe)" -> Under Treatment, and "Treatment
outcome = Recovered/Plant lost" -> In Production/Deceased.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.db.enums import DiseaseReportSeverity, DiseaseReportStatus, PlantStatus, TreatmentOutcome
from app.domain_events import DiseaseDetected, DiseaseReportUpdated, DomainEventPublisher, TreatmentApplied
from app.models.disease import DiseaseReport, Treatment
from app.models.platform import AuditLog
from app.repositories.interfaces import AuditLogRepository, DiseaseReportRepository, TreatmentRepository
from app.services.plant_service import PlantService

# Only these severities force the plant straight into Under Treatment on
# confirmation -- a confirmed LOW-severity report is logged and tracked
# but doesn't by itself pull a plant out of active/sellable circulation,
# consistent with "severity threshold" language in the lifecycle doc's
# own transition-rules table ("Disease report confirmed above severity
# threshold").
_AUTO_TREATMENT_SEVERITIES = {
    DiseaseReportSeverity.MEDIUM,
    DiseaseReportSeverity.HIGH,
    DiseaseReportSeverity.CRITICAL,
}


class DiseaseReportService:
    def __init__(
        self,
        *,
        disease_repo: DiseaseReportRepository,
        plant_service: PlantService,
        audit_repo: AuditLogRepository,
        event_publisher: DomainEventPublisher,
    ) -> None:
        self._reports = disease_repo
        self._plants = plant_service
        self._audit = audit_repo
        self._events = event_publisher

    async def create_report(
        self,
        *,
        plant_id: uuid.UUID,
        condition_name: str,
        severity: DiseaseReportSeverity,
        actor_user_id: uuid.UUID,
        is_ai_sourced: bool = False,
        ai_confidence: float | None = None,
        source_ai_prediction_id: uuid.UUID | None = None,
        photo_url: str | None = None,
        request_id: str | None = None,
    ) -> DiseaseReport:
        """Draft report -- manual (a human logs it directly) or the landing spot for a future AI Disease Detection module's above-threshold result (FR-7.2)."""
        if not condition_name or not condition_name.strip():
            raise ValidationError("condition_name is required.")
        plant = await self._plants.get_plant(plant_id)  # raises NotFoundError if missing -- also confirms the plant exists before we attach a report to it

        report = DiseaseReport(
            plant_id=plant_id,
            condition_name=condition_name.strip(),
            status=DiseaseReportStatus.DRAFT,
            severity=severity,
            is_ai_sourced=is_ai_sourced,
            ai_confidence=ai_confidence,
            source_ai_prediction_id=source_ai_prediction_id,
            photo_url=photo_url,
            created_at=datetime.now(timezone.utc),
        )
        await self._reports.add(report)

        await self._log_audit(
            nursery_id=plant.nursery_id, actor_user_id=actor_user_id, action="plant.disease_detected",
            entity_id=plant_id, diff={"after": {"disease_report_id": str(report.id), "severity": severity.value}},
            request_id=request_id,
        )
        await self._events.publish(
            DiseaseDetected(
                aggregate_id=plant_id, nursery_id=plant.nursery_id, actor_user_id=actor_user_id,
                disease_report_id=report.id, condition_name=report.condition_name, severity=severity.value,
            ),
            request_id=request_id,
        )
        return report

    async def confirm_report(
        self, *, report_id: uuid.UUID, actor_user_id: uuid.UUID, request_id: str | None = None
    ) -> DiseaseReport:
        """`disease:approve` (narrower than `disease:write`) is the permission this action requires -- enforced at the route layer, per the module's own permission matrix."""
        report = await self._get_report(report_id)
        if report.status != DiseaseReportStatus.DRAFT:
            raise ConflictError(f"Only a draft report can be confirmed (this one is '{report.status.value}').")

        report.status = DiseaseReportStatus.CONFIRMED
        report.confirmed_by_user_id = actor_user_id
        report.confirmed_at = datetime.now(timezone.utc)

        plant = await self._plants.get_plant(report.plant_id)
        if report.severity in _AUTO_TREATMENT_SEVERITIES and plant.status in (
            PlantStatus.IN_PRODUCTION,
            PlantStatus.READY_FOR_SALE,
        ):
            await self._plants.transition_status(
                plant_id=report.plant_id, to_status=PlantStatus.UNDER_TREATMENT, actor_user_id=actor_user_id,
                reason=f"Disease report confirmed: {report.condition_name}", request_id=request_id,
            )

        await self._update_and_notify(report, actor_user_id=actor_user_id, request_id=request_id, nursery_id=plant.nursery_id)
        return report

    async def dismiss_report(
        self, *, report_id: uuid.UUID, actor_user_id: uuid.UUID, dismissed_reason: str, request_id: str | None = None
    ) -> DiseaseReport:
        report = await self._get_report(report_id)
        if report.status != DiseaseReportStatus.DRAFT:
            raise ConflictError(f"Only a draft report can be dismissed (this one is '{report.status.value}').")
        if not dismissed_reason or not dismissed_reason.strip():
            raise ValidationError("dismissed_reason is required.")

        report.status = DiseaseReportStatus.DISMISSED
        report.dismissed_reason = dismissed_reason.strip()

        plant = await self._plants.get_plant(report.plant_id)
        await self._update_and_notify(report, actor_user_id=actor_user_id, request_id=request_id, nursery_id=plant.nursery_id)
        return report

    async def get_report(self, report_id: uuid.UUID) -> DiseaseReport:
        return await self._get_report(report_id)

    async def list_for_plant(self, plant_id: uuid.UUID) -> list[DiseaseReport]:
        await self._plants.get_plant(plant_id)
        return await self._reports.list_for_plant(plant_id)

    async def list_for_nursery(
        self,
        *,
        nursery_id: uuid.UUID,
        offset: int,
        limit: int,
        status: DiseaseReportStatus | None = None,
        severity: DiseaseReportSeverity | None = None,
    ) -> tuple[list[DiseaseReport], int]:
        return await self._reports.list_for_nursery(
            nursery_id, offset=offset, limit=limit, status=status, severity=severity
        )

    async def _get_report(self, report_id: uuid.UUID) -> DiseaseReport:
        report = await self._reports.get_by_id(report_id)
        if report is None:
            raise NotFoundError("Disease report not found.")
        return report

    async def _update_and_notify(
        self, report: DiseaseReport, *, actor_user_id: uuid.UUID, request_id: str | None, nursery_id: uuid.UUID
    ) -> None:
        await self._log_audit(
            nursery_id=nursery_id, actor_user_id=actor_user_id, action="plant.disease_report_updated",
            entity_id=report.plant_id, diff={"after": {"disease_report_id": str(report.id), "status": report.status.value}},
            request_id=request_id,
        )
        await self._events.publish(
            DiseaseReportUpdated(
                aggregate_id=report.plant_id, nursery_id=nursery_id, actor_user_id=actor_user_id,
                disease_report_id=report.id, status=report.status.value,
            ),
            request_id=request_id,
        )

    async def _log_audit(
        self, *, nursery_id: uuid.UUID, actor_user_id: uuid.UUID, action: str, entity_id: uuid.UUID,
        diff: dict, request_id: str | None,
    ) -> None:
        await self._audit.log(
            AuditLog(
                nursery_id=nursery_id, actor_user_id=actor_user_id, action=action, entity_type="Plant",
                entity_id=entity_id, diff=diff, request_id=request_id, created_at=datetime.now(timezone.utc),
            )
        )


class TreatmentService:
    def __init__(
        self,
        *,
        treatment_repo: TreatmentRepository,
        disease_repo: DiseaseReportRepository,
        plant_service: PlantService,
        audit_repo: AuditLogRepository,
        event_publisher: DomainEventPublisher,
    ) -> None:
        self._treatments = treatment_repo
        self._reports = disease_repo
        self._plants = plant_service
        self._audit = audit_repo
        self._events = event_publisher

    async def apply_treatment(
        self,
        *,
        disease_report_id: uuid.UUID,
        description: str,
        outcome: TreatmentOutcome,
        actor_user_id: uuid.UUID,
        request_id: str | None = None,
    ) -> Treatment:
        """
        FR-7.3. A report can accumulate multiple treatment attempts before
        an outcome closes it. `outcome=ONGOING` logs progress without
        closing the report or moving the plant out of Under Treatment;
        `RECOVERED`/`PLANT_LOST` close the report (-> RESOLVED) and drive
        the matching Plant status transition, exactly the lifecycle doc's
        "Treatment outcome = Recovered/Plant lost" trigger.
        """
        if not description or not description.strip():
            raise ValidationError("description is required.")

        report = await self._reports.get_by_id(disease_report_id)
        if report is None:
            raise NotFoundError("Disease report not found.")
        if report.status == DiseaseReportStatus.RESOLVED:
            raise ConflictError("This disease report is already resolved -- no further treatment can be logged against it.")

        treatment = Treatment(
            disease_report_id=disease_report_id, description=description.strip(), outcome=outcome,
            applied_by_user_id=actor_user_id, applied_at=datetime.now(timezone.utc),
        )
        await self._treatments.add(treatment)

        if outcome == TreatmentOutcome.ONGOING and report.status == DiseaseReportStatus.CONFIRMED:
            report.status = DiseaseReportStatus.TREATED

        plant = await self._plants.get_plant(report.plant_id)

        if outcome in (TreatmentOutcome.RECOVERED, TreatmentOutcome.PLANT_LOST):
            report.status = DiseaseReportStatus.RESOLVED
            report.resolved_at = datetime.now(timezone.utc)
            if plant.status == PlantStatus.UNDER_TREATMENT:
                to_status = PlantStatus.IN_PRODUCTION if outcome == TreatmentOutcome.RECOVERED else PlantStatus.DECEASED
                await self._plants.transition_status(
                    plant_id=report.plant_id, to_status=to_status, actor_user_id=actor_user_id,
                    reason=f"Treatment outcome: {outcome.value}", request_id=request_id,
                )

        await self._log_audit(
            nursery_id=plant.nursery_id, actor_user_id=actor_user_id, action="plant.treatment_applied",
            entity_id=report.plant_id,
            diff={"after": {"treatment_id": str(treatment.id), "outcome": outcome.value}},
            request_id=request_id,
        )
        await self._events.publish(
            TreatmentApplied(
                aggregate_id=report.plant_id, nursery_id=plant.nursery_id, actor_user_id=actor_user_id,
                disease_report_id=disease_report_id, treatment_id=treatment.id, outcome=outcome.value,
            ),
            request_id=request_id,
        )
        return treatment

    async def list_for_report(self, disease_report_id: uuid.UUID) -> list[Treatment]:
        return await self._treatments.list_for_disease_report(disease_report_id)

    async def _log_audit(
        self, *, nursery_id: uuid.UUID, actor_user_id: uuid.UUID, action: str, entity_id: uuid.UUID,
        diff: dict, request_id: str | None,
    ) -> None:
        await self._audit.log(
            AuditLog(
                nursery_id=nursery_id, actor_user_id=actor_user_id, action=action, entity_type="Plant",
                entity_id=entity_id, diff=diff, request_id=request_id, created_at=datetime.now(timezone.utc),
            )
        )
