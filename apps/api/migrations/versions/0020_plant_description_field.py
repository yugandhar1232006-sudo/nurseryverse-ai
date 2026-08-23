"""Add description field to plants table.

Revision ID: 0020
Revises: 0019
Create Date: 2026-08-18

Adds an optional `description` TEXT column to `plants` for free-text
notes about a plant record. Nullable, no default -- backward-compatible
with all existing rows.
"""
import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("plants", sa.Column("description", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("plants", "description")
