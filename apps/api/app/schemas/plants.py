"""Pydantic request/response DTOs for Module 6 (Plant Lifecycle Management)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.db.enums import DiseaseReportSeverity, DiseaseReportStatus, PlantStatus, TreatmentOutcome

# ==============================================================================
# Plant Registration / Profile
# ==============================================================================


class RegisterPlantRequest(BaseModel):
    branch_id: uuid.UUID
    species_id: uuid.UUID
    variety_id: uuid.UUID | None = None
    common_label: str | None = Field(None, max_length=255)
    zone: str | None = Field(None, max_length=100)
    batch_number: str | None = Field(None, max_length=100)
    supplier_id: uuid.UUID | None = None
    purchase_price: float | None = Field(None, ge=0)
    purchase_date: datetime | None = None
    price: float | None = Field(None, ge=0)
    planted_at: datetime | None = None
    description: str | None = Field(None, max_length=5000)


class BulkRegisterPlantsRequest(BaseModel):
    plants: list[RegisterPlantRequest] = Field(..., min_length=1, max_length=500)


class UpdatePlantProfileRequest(BaseModel):
    common_label: str | None = Field(None, max_length=255)
    variety_id: uuid.UUID | None = None
    batch_number: str | None = Field(None, max_length=100)
    supplier_id: uuid.UUID | None = None
    purchase_price: float | None = Field(None, ge=0)
    purchase_date: datetime | None = None
    price: float | None = Field(None, ge=0)
    description: str | None = Field(None, max_length=5000)


class TransitionStatusRequest(BaseModel):
    to_status: PlantStatus
    reason: str | None = None


class MovePlantRequest(BaseModel):
    to_branch_id: uuid.UUID | None = None
    to_zone: str | None = Field(None, max_length=100)
    note: str | None = None


class ArchivePlantRequest(BaseModel):
    reason: str | None = None


class UploadPlantImageRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=1000)
    thumbnail_url: str | None = Field(None, max_length=1000)
    caption: str | None = Field(None, max_length=255)


class PlantImageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plant_id: uuid.UUID
    url: str
    thumbnail_url: str | None
    caption: str | None
    captured_at: datetime
    uploaded_by_user_id: uuid.UUID | None


class PlantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nursery_id: uuid.UUID
    branch_id: uuid.UUID
    species_id: uuid.UUID
    variety_id: uuid.UUID | None
    common_label: str | None
    zone: str | None
    status: PlantStatus
    qr_code_token: str
    price: float | None
    planted_at: datetime
    sold_at: datetime | None
    deceased_at: datetime | None
    deceased_reason: str | None
    batch_number: str | None
    supplier_id: uuid.UUID | None
    purchase_price: float | None
    purchase_date: datetime | None
    registered_by_user_id: uuid.UUID | None
    archived_at: datetime | None
    archived_reason: str | None
    description: str | None
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def age_days(self) -> int:
        """Plant Profile's "Age" -- always derived from `planted_at`, never stored (there is nothing to keep in sync), and serialized into every PlantResponse via Pydantic v2's `@computed_field`."""
        planted = self.planted_at if self.planted_at.tzinfo else self.planted_at.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - planted).days


class PlantTransferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plant_id: uuid.UUID
    from_branch_id: uuid.UUID
    to_branch_id: uuid.UUID
    from_zone: str | None
    to_zone: str | None
    note: str | None
    transferred_by_user_id: uuid.UUID
    transferred_at: datetime


# ==============================================================================
# Growth / Health / Watering / Fertilizer / Environmental Records
# ==============================================================================


class RecordGrowthRequest(BaseModel):
    height_cm: float | None = Field(None, ge=0)
    spread_cm: float | None = Field(None, ge=0)
    leaf_count: int | None = Field(None, ge=0)
    flower_count: int | None = Field(None, ge=0)
    fruit_count: int | None = Field(None, ge=0)
    growth_stage: str | None = Field(None, max_length=50, description="Free-text, e.g. 'seedling', 'growing', 'mature'")
    notes: str | None = None
    photo_urls: list[str] | None = None
    measured_at: datetime | None = None


class GrowthRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plant_id: uuid.UUID
    height_cm: float | None
    spread_cm: float | None
    leaf_count: int | None
    flower_count: int | None
    fruit_count: int | None
    growth_stage: str | None
    photo_url: str | None
    photo_urls: list | None
    notes: str | None
    recorded_by_user_id: uuid.UUID
    recorded_at: datetime


class RecordHealthRequest(BaseModel):
    status_label: str = Field(..., min_length=1, max_length=50)
    health_score: float | None = Field(None, ge=0, le=100)
    notes: str | None = None
    photo_url: str | None = Field(None, max_length=1000)
    is_ai_observation: bool = False
    observed_at: datetime | None = None


class HealthRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plant_id: uuid.UUID
    status_label: str
    health_score: float | None
    notes: str | None
    photo_url: str | None
    is_ai_observation: bool
    recorded_by_user_id: uuid.UUID
    recorded_at: datetime


class RecordWateringRequest(BaseModel):
    volume_ml: float | None = Field(None, ge=0)
    method: str | None = Field(None, max_length=50)
    notes: str | None = None
    watered_at: datetime | None = None


class WateringRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plant_id: uuid.UUID
    branch_id: uuid.UUID
    zone: str | None
    volume_ml: float | None
    method: str | None
    notes: str | None
    recorded_by_user_id: uuid.UUID
    recorded_at: datetime


class RecordFertilizerRequest(BaseModel):
    product_name: str = Field(..., min_length=1, max_length=255)
    quantity_ml: float | None = Field(None, ge=0)
    npk_ratio: str | None = Field(None, max_length=20)
    method: str | None = Field(None, max_length=50)
    schedule: str | None = Field(None, max_length=50)
    next_application_date: datetime | None = None
    notes: str | None = None
    applied_at: datetime | None = None


class FertilizerRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plant_id: uuid.UUID
    branch_id: uuid.UUID
    zone: str | None
    product_name: str
    quantity_ml: float | None
    npk_ratio: str | None
    method: str | None
    schedule: str | None
    next_application_date: datetime | None
    notes: str | None
    recorded_by_user_id: uuid.UUID
    recorded_at: datetime


class RecordEnvironmentalRequest(BaseModel):
    temperature_celsius: float | None = None
    humidity_percent: float | None = Field(None, ge=0, le=100)
    soil_moisture_percent: float | None = Field(None, ge=0, le=100)
    light_lux: float | None = Field(None, ge=0)
    ph_level: float | None = Field(None, ge=0, le=14)
    weather_snapshot: dict | None = None
    source: str = Field("manual", max_length=20)
    recorded_at: datetime | None = None


class EnvironmentalRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plant_id: uuid.UUID
    branch_id: uuid.UUID
    zone: str | None
    temperature_celsius: float | None
    humidity_percent: float | None
    soil_moisture_percent: float | None
    light_lux: float | None
    ph_level: float | None
    weather_snapshot: dict | None
    source: str
    recorded_at: datetime


# ==============================================================================
# Disease Reports / Treatments
# ==============================================================================


class CreateDiseaseReportRequest(BaseModel):
    condition_name: str = Field(..., min_length=1, max_length=255)
    severity: DiseaseReportSeverity
    is_ai_sourced: bool = False
    ai_confidence: float | None = Field(None, ge=0, le=1)
    photo_url: str | None = Field(None, max_length=1000)


class DismissDiseaseReportRequest(BaseModel):
    dismissed_reason: str = Field(..., min_length=1)


class DiseaseReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plant_id: uuid.UUID
    condition_name: str
    status: DiseaseReportStatus
    severity: DiseaseReportSeverity
    is_ai_sourced: bool
    ai_confidence: float | None
    photo_url: str | None
    confirmed_by_user_id: uuid.UUID | None
    confirmed_at: datetime | None
    dismissed_reason: str | None
    resolved_at: datetime | None
    created_at: datetime


class ApplyTreatmentRequest(BaseModel):
    description: str = Field(..., min_length=1)
    outcome: TreatmentOutcome


class TreatmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    disease_report_id: uuid.UUID
    description: str
    outcome: TreatmentOutcome
    applied_by_user_id: uuid.UUID
    applied_at: datetime


# ==============================================================================
# Timeline
# ==============================================================================


class PlantTimelineEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_type: str
    occurred_at: datetime
    summary: str
    source_id: uuid.UUID
    actor_user_id: uuid.UUID | None
