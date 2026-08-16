"""
AI bounded context: AIPrediction (the universal logging contract, FR-8.7),
AIRecommendation, and the AI Assistant's conversation history.

Maps to docs/architecture/02-low-level-design.md "Module: AI Predictions"
and "Module: AI Assistant", and docs/architecture/06-ai-architecture.md §3
(Inference Pipeline) / §10 (Model Versioning).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Enum as PgEnum
from sqlalchemy import JSON, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.enums import AIPredictionType, AIRecommendationStatus

# Embedding dimension for the AI Assistant's RAG knowledge base. 1024 matches
# Voyage AI's voyage-3 / voyage-2 models (Anthropic's recommended embedding
# provider, since Claude does not serve embeddings directly). If Phase 8
# selects a different embedding model, this constant -- and the `Vector(...)`
# column below -- must change together with a new migration; pgvector
# requires a fixed dimension per column.
EMBEDDING_DIM = 1024


class AIPrediction(UUIDPKMixin, Base):
    """
    The single table every one of the six AI prediction modules writes to
    (FR-8.7's "no AI output without a persisted record" contract, enforced
    structurally by PredictionLogger — docs/architecture/06-ai-architecture.md
    §3). `plant_id` is null for org/branch-level predictions (Revenue
    Forecast); `branch_id`/`nursery_id` are always set for tenant scoping
    regardless of prediction level.
    """

    __tablename__ = "ai_predictions"
    __table_args__ = (
        Index("ix_ai_predictions_plant_type_created", "plant_id", "prediction_type", "created_at"),
        Index("ix_ai_predictions_nursery_branch", "nursery_id", "branch_id"),
    )

    nursery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nurseries.id", ondelete="CASCADE"), nullable=False
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id", ondelete="CASCADE"), nullable=True
    )
    plant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plants.id", ondelete="CASCADE"), nullable=True
    )
    prediction_type: Mapped[AIPredictionType] = mapped_column(
        PgEnum(AIPredictionType, name="ai_prediction_type"), nullable=False
    )
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    result: Mapped[dict] = mapped_column(JSON, nullable=False)  # module-specific payload
    confidence: Mapped[Numeric | None] = mapped_column(Numeric(5, 4), nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    inputs_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)

    # Added by Phase 6 Module 13 ("AI Administration" -- inference latency).
    # Measured once, in `InferenceBase.run()` (the one place every
    # prediction module's `predict()` call passes through, per this
    # module's own docstring), around the `preprocess -> predict ->
    # postprocess` sequence -- never re-derived or estimated here.
    # Nullable because every `AIPrediction` row written before this column
    # existed has no recorded latency, and this is a metric, not a
    # required business fact.
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class AIRecommendation(UUIDPKMixin, Base):
    """FR-8.6. Recommendation Engine output — mutable status (dismiss/act)."""

    __tablename__ = "ai_recommendations"
    __table_args__ = (Index("ix_ai_recommendations_branch_status", "branch_id", "status"),)

    nursery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nurseries.id", ondelete="CASCADE"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False
    )
    source_prediction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_predictions.id", ondelete="SET NULL"), nullable=True
    )
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    deep_link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[AIRecommendationStatus] = mapped_column(
        PgEnum(AIRecommendationStatus, name="ai_recommendation_status"),
        nullable=False,
        default=AIRecommendationStatus.NEW,
    )
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)


class AIInferenceFailure(UUIDPKMixin, Base):
    """
    Added by Phase 6 Module 13 ("AI Administration" -- AI failures).
    `PredictionLogger.persist()` is the only writer of a SUCCESSFUL
    `AIPrediction` row (that class's own docstring); this table is its
    exact counterpart for the failure path -- `InferenceBase.run()`
    catches any exception raised by `preprocess`/`predict`/`postprocess`,
    writes one row here (never swallowing the error -- it still re-raises
    to the caller afterward, so every prediction module's existing
    typed-error-to-graceful-degradation behavior, e.g. `ModelUnavailableError`,
    is completely unchanged), and only THEN re-raises. Read-only from the
    application's perspective otherwise -- `AIAdminService` aggregates
    over it for the admin dashboard's "AI failures" panel; nothing ever
    updates or retries a row here directly (a retry is a brand new
    inference call, which either succeeds and writes an `AIPrediction`, or
    fails again and writes another row here).
    """

    __tablename__ = "ai_inference_failures"
    __table_args__ = (Index("ix_ai_inference_failures_nursery_created", "nursery_id", "created_at"),)

    nursery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nurseries.id", ondelete="CASCADE"), nullable=False
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id", ondelete="CASCADE"), nullable=True
    )
    capability: Mapped[str] = mapped_column(String(50), nullable=False)  # InferenceBase.capability, e.g. "disease_detection"
    prediction_type: Mapped[str] = mapped_column(String(50), nullable=False)  # AIPredictionType.value -- plain str, not the enum column type, so a future prediction type never needs a migration just to be loggable as a failure
    error_type: Mapped[str] = mapped_column(String(200), nullable=False)  # exception class name, e.g. "ModelUnavailableError"
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)


class AIAssistantConversation(UUIDPKMixin, TimestampMixin, Base):
    """FR-9.4. Per-user conversation thread."""

    __tablename__ = "ai_assistant_conversations"
    __table_args__ = (Index("ix_ai_assistant_conversations_user_id", "user_id"),)

    nursery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nurseries.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    messages: Mapped[list["AIAssistantMessage"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class AIAssistantMessage(UUIDPKMixin, Base):
    """
    Append-only. `proposed_action` / `action_status` implement FR-9.3's
    mandatory human-confirmation gate for any assistant-proposed write.
    """

    __tablename__ = "ai_assistant_messages"
    __table_args__ = (Index("ix_ai_assistant_messages_conversation_id", "conversation_id"),)

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_assistant_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_action: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    action_status: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )  # pending_confirmation | confirmed | cancelled
    created_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)

    # Added by Phase 6 Module 10 (migration 0015) -- "cost tracking"/"token
    # usage analytics". Null on every `role="user"` row (never sent to a
    # model); populated on `role="assistant"` rows from the underlying
    # `AssistantOrchestrator`/Anthropic API response's own usage block.
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[Numeric | None] = mapped_column(Numeric(10, 6), nullable=True)

    conversation: Mapped["AIAssistantConversation"] = relationship(back_populates="messages")


class KnowledgeBaseChunk(UUIDPKMixin, TimestampMixin, Base):
    """
    RAG grounding store for the AI Assistant (FR-9.1 "answers are grounded
    in the org's real data and curated horticultural knowledge, not model
    hallucination"). Added by the Production Database Readiness Review
    (docs/architecture/17-production-database-readiness-review.md §5): the
    pgvector extension was enabled in migration 0001 from the start, but no
    table actually carried a `vector` column until now -- meaning the RAG
    half of the AI Architecture (docs/architecture/06-ai-architecture.md §7)
    had no schema to write to. This closes that gap.

    Two source kinds share one table rather than being split, because the
    Assistant's retrieval step queries both together in a single similarity
    search: `source_type='org_data'` rows are short, periodically
    regenerated summaries of an org's own records (a plant's care history, a
    branch's current inventory position) scoped by `nursery_id`;
    `source_type='knowledge_article'` rows are curated, platform-wide
    horticultural reference content (species care guides, disease
    treatment guides) with `nursery_id` NULL, shared across every tenant.
    RLS (migration 0003) is intentionally NOT applied to this table for the
    same reason it's not applied to `plant_categories`/`units` -- knowledge
    articles are global by design -- so tenant isolation for `org_data` rows
    is enforced at the application/query layer (the retrieval service always
    filters `nursery_id = :current_org OR source_type = 'knowledge_article'`
    explicitly), not by RLS.
    """

    __tablename__ = "knowledge_base_chunks"
    __table_args__ = (
        Index("ix_knowledge_base_chunks_nursery_source", "nursery_id", "source_type"),
        # HNSW over ivfflat: no training/ANALYZE step required before the
        # index is usable, which matters because this table starts empty
        # and is populated incrementally by an ingestion job (Phase 8), not
        # bulk-loaded once. Cosine distance matches Voyage AI's recommended
        # similarity metric for their embeddings.
        Index(
            "ix_knowledge_base_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    nursery_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nurseries.id", ondelete="CASCADE"), nullable=True
    )
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)  # org_data | knowledge_article
    source_ref: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )  # e.g. "plant:<uuid>", "species:<uuid>", or a curated-article slug
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)  # the chunked text that was embedded
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    embedding_model_version: Mapped[str] = mapped_column(String(50), nullable=False)
