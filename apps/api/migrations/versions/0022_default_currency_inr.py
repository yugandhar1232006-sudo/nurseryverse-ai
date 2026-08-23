"""Change default currency from USD to INR.

Revision ID: 0022
Revises: 0021
Create Date: 2026-08-19
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

NURSERY_ID = "0bdea99c-565b-4992-a743-4462079e5a72"


def upgrade() -> None:
    op.alter_column(
        "org_settings",
        "default_currency",
        server_default="INR",
    )
    op.execute(
        sa.text(
            f"UPDATE org_settings SET default_currency = 'INR' "
            f"WHERE nursery_id = '{NURSERY_ID}'::uuid"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            f"UPDATE org_settings SET default_currency = 'USD' "
            f"WHERE nursery_id = '{NURSERY_ID}'::uuid"
        )
    )
    op.alter_column(
        "org_settings",
        "default_currency",
        server_default="USD",
    )
