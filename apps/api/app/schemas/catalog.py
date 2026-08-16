"""Pydantic request/response DTOs for Module 5's Species Catalog (FR-4)."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PlantCategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    description: str | None


class GrowthCurvePoint(BaseModel):
    days_since_planting: int = Field(..., ge=0)
    expected_height_cm: float = Field(..., ge=0)


class CreateSpeciesRequest(BaseModel):
    category_id: uuid.UUID
    common_name: str = Field(..., min_length=1, max_length=255)
    botanical_name: str = Field(..., min_length=1, max_length=255)
    light_requirement: str | None = Field(None, max_length=50)
    water_baseline_ml_per_week: int | None = Field(None, ge=0)
    soil_type: str | None = Field(None, max_length=100)
    temperature_min_celsius: float | None = None
    temperature_max_celsius: float | None = None
    growth_curve_baseline: list[GrowthCurvePoint] | None = None
    disease_susceptibility: list[str] | None = None


class UpdateSpeciesRequest(BaseModel):
    category_id: uuid.UUID | None = None
    common_name: str | None = Field(None, min_length=1, max_length=255)
    botanical_name: str | None = Field(None, min_length=1, max_length=255)
    light_requirement: str | None = Field(None, max_length=50)
    water_baseline_ml_per_week: int | None = Field(None, ge=0)
    soil_type: str | None = Field(None, max_length=100)
    temperature_min_celsius: float | None = None
    temperature_max_celsius: float | None = None
    growth_curve_baseline: list[GrowthCurvePoint] | None = None
    disease_susceptibility: list[str] | None = None


class SpeciesResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nursery_id: uuid.UUID
    category_id: uuid.UUID
    common_name: str
    botanical_name: str
    light_requirement: str | None
    water_baseline_ml_per_week: int | None
    soil_type: str | None
    temperature_min_celsius: float | None
    temperature_max_celsius: float | None
    growth_curve_baseline: list | None
    disease_susceptibility: list | None
    created_at: datetime
    updated_at: datetime


class CreatePlantVarietyRequest(BaseModel):
    species_id: uuid.UUID
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=500)


class UpdatePlantVarietyRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=500)


class PlantVarietyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nursery_id: uuid.UUID
    species_id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
