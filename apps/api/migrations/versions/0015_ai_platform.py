"""AI Platform (Phase 6 Module 10).

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-07

Evolves the Phase 5 `ai_predictions`/`ai_recommendations`/
`ai_assistant_conversations`/`ai_assistant_messages`/`knowledge_base_chunks`
skeleton (all already present since migration 0001, all already RLS-covered
since migration 0003) into the bounded context Module 10's spec requires --
the same "first module to actually build on a pre-existing table" pattern
Module 5 applied to species/categories, Module 6 to plants, Module 8 to
inventory, Module 9 to customers/sales/passports. See
docs/architecture/06-ai-architecture.md and app/models/ai.py's module
docstring for the full architectural reasoning (why six prediction modules
share one `ai_predictions` logging table, why the AI Assistant's
conversation/message tables are separate from that).

One move, deliberately narrow: `ai_assistant_messages` gains four columns
this module's own spec explicitly calls for ("cost tracking," "token usage
analytics") that the Phase 5 skeleton has nowhere to record --
`model_name`, `input_tokens`, `output_tokens`, `cost_usd`. All nullable
(a `role="user"` row was never sent to a model and has none of these; a
`role="assistant"` row populates all four once the underlying
`AssistantOrchestrator` call returns). No other schema change is needed:
`ai_predictions.model_version` (Phase 5) already satisfies FR-8.7's
"persisted with model version" requirement for the six prediction modules,
`ai_predictions.confidence`/`explanation`/`inputs_summary` already satisfy
the rest of that same requirement, and `ai_recommendations.status` already
satisfies the Recommendation Engine's dismiss/act mutable-status
requirement -- none of that needed to be re-added here.

No new RLS policies: `ai_predictions`/`ai_recommendations`/
`ai_assistant_conversations` (direct tenant_id) and `ai_assistant_messages`
(join-scoped through `ai_assistant_conversations`) are already covered by
migration 0003. `knowledge_base_chunks` remains deliberately RLS-exempt,
per that table's own docstring in app/models/ai.py (global knowledge
articles + app-layer-filtered org_data rows, the same pattern already used
for `plant_categories`/`units`).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ai_assistant_messages", sa.Column("model_name", sa.String(100), nullable=True))
    op.add_column("ai_assistant_messages", sa.Column("input_tokens", sa.Integer(), nullable=True))
    op.add_column("ai_assistant_messages", sa.Column("output_tokens", sa.Integer(), nullable=True))
    op.add_column(
        "ai_assistant_messages", sa.Column("cost_usd", sa.Numeric(10, 6), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("ai_assistant_messages", "cost_usd")
    op.drop_column("ai_assistant_messages", "output_tokens")
    op.drop_column("ai_assistant_messages", "input_tokens")
    op.drop_column("ai_assistant_messages", "model_name")
