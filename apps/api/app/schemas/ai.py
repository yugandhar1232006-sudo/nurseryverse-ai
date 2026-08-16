"""Pydantic request/response DTOs for Module 10 (AI Platform) -- both the six prediction modules and the AI Assistant."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.db.enums import AIPredictionType, AIRecommendationStatus

# ==============================================================================
# AI Predictions (FR-8.1-8.5, 8.7, 8.8)
# ==============================================================================


class RunDiseaseDetectionRequest(BaseModel):
    plant_id: uuid.UUID
    image_url: str = Field(..., min_length=1, max_length=1000, description="Cloudinary-hosted, normalized plant-photo derivative.")


class AIPredictionResponse(BaseModel):
    # `protected_namespaces=()`: this table's own column is named `model_version` (the AI/ML sense of
    # "model", per FR-8.7's versioning requirement) -- unrelated to Pydantic's "model_*" reserved-attribute
    # convention it would otherwise warn about colliding with.
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: uuid.UUID
    nursery_id: uuid.UUID
    branch_id: uuid.UUID | None
    plant_id: uuid.UUID | None
    prediction_type: AIPredictionType
    model_version: str
    result: dict[str, Any]
    confidence: Decimal | None
    explanation: str | None
    inputs_summary: dict[str, Any] | None
    created_at: datetime


class AIRecommendationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: uuid.UUID
    nursery_id: uuid.UUID
    branch_id: uuid.UUID
    source_prediction_id: uuid.UUID | None
    priority: str
    summary: str
    explanation: str | None
    deep_link: str | None
    status: AIRecommendationStatus
    model_version: str
    created_at: datetime


# ==============================================================================
# AI Assistant (FR-9.1-9.4)
# ==============================================================================


class SendAssistantMessageRequest(BaseModel):
    conversation_id: uuid.UUID | None = Field(
        None, description="Omit to start a new conversation; provide to continue an existing one you own."
    )
    content: str = Field(..., min_length=1, max_length=4000)


class ConfirmAssistantActionRequest(BaseModel):
    conversation_id: uuid.UUID = Field(..., description="The conversation this proposed action belongs to (for ownership verification).")
    confirm: bool = Field(
        True,
        description=(
            "true = execute the proposed action through its normal service-layer validation path (FR-9.3); "
            "false = discard the proposal with no side effect (docs/ux/12-ai-workflow-diagrams.md §7's "
            "'No' branch). Both are the same endpoint, matching the LLD's single documented confirm route."
        ),
    )


class AssistantMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    proposed_action: dict[str, Any] | None
    action_status: str | None
    model_name: str | None
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: Decimal | None
    created_at: datetime


class AssistantConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nursery_id: uuid.UUID
    user_id: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime


class AssistantConversationDetailResponse(BaseModel):
    """`GET /ai/assistant/conversations/{id}` -- the conversation's own metadata plus its paginated message log."""

    conversation: AssistantConversationResponse
    messages: list[AssistantMessageResponse]
    total_messages: int
