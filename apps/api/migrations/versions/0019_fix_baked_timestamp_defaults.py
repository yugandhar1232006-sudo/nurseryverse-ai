"""Fix baked timestamp defaults.

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-16

Migration 0001 declared a subset of timestamp columns with
`server_default='now()'` -- a plain string. SQLAlchemy 2.x renders a
plain-string server_default as a quoted literal, so PostgreSQL baked the
literal DDL time (`'2026-08-16 07:19:04.776616+00'`) into each column's
default instead of the `now()` function. Every row inserted through that
default then shared the same migration-time timestamp, breaking
newest-first ordering and any timestamp-based display/logic for the
affected tables.

The 0001 source has been corrected to `server_default=sa.text('now()')`
(see `git diff 0018`), which makes fresh installs correct. This migration
repairs databases that already ran the buggy 0001 by re-asserting the
`now()` function default on the affected columns; it is a no-op for fresh
installs (the default is already `now()`).

Affected columns (created by 0001, one per line):
  ai_assistant_messages.created_at, ai_predictions.created_at,
  ai_recommendations.created_at, attachments.uploaded_at,
  audit_logs.created_at, authorization_denials.created_at,
  disease_reports.created_at, email_verification_tokens.created_at,
  environmental_readings.recorded_at, fertilizer_logs.recorded_at,
  growth_timeline.recorded_at, health_history.recorded_at,
  notifications.created_at, passports.generated_at,
  password_reset_tokens.created_at, payments.received_at,
  plant_images.captured_at, plant_transfers.transferred_at,
  refresh_tokens.issued_at, reports.created_at, sales.created_at,
  security_events.created_at, stock_movements.created_at,
  treatments.applied_at, watering_logs.recorded_at
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

AFFECTED_COLUMNS: list[tuple[str, str]] = [
    ("ai_assistant_messages", "created_at"),
    ("ai_predictions", "created_at"),
    ("ai_recommendations", "created_at"),
    ("attachments", "uploaded_at"),
    ("audit_logs", "created_at"),
    ("authorization_denials", "created_at"),
    ("disease_reports", "created_at"),
    ("email_verification_tokens", "created_at"),
    ("environmental_readings", "recorded_at"),
    ("fertilizer_logs", "recorded_at"),
    ("growth_timeline", "recorded_at"),
    ("health_history", "recorded_at"),
    ("notifications", "created_at"),
    ("passports", "generated_at"),
    ("password_reset_tokens", "created_at"),
    ("payments", "received_at"),
    ("plant_images", "captured_at"),
    ("plant_transfers", "transferred_at"),
    ("refresh_tokens", "issued_at"),
    ("reports", "created_at"),
    ("sales", "created_at"),
    ("security_events", "created_at"),
    ("stock_movements", "created_at"),
    ("treatments", "applied_at"),
    ("watering_logs", "recorded_at"),
]


def upgrade() -> None:
    for table, column in AFFECTED_COLUMNS:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT now();"
        )


def downgrade() -> None:
    # The buggy baked-literal default this migration repaired is not
    # reproducible (it was the migration 0001 DDL time, now lost), so
    # downgrade is intentionally a no-op.
    pass
