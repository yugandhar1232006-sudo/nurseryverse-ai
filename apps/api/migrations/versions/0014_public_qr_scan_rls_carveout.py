"""Public QR scan RLS carve-out (Phase 6 Module 9 follow-up).

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-07

WHY THIS MIGRATION EXISTS. Module 9's QR Intelligence spec requires that
scanning a QR (no authentication) returns live Health Status, Growth
Timeline, and Fertilizer Schedule data -- not just the frozen
`Passport.content_snapshot` (see `QRService.scan`'s own docstring on the
deliberate frozen-vs-live asymmetry). `QRService.scan` reads
`plants`/`growth_timeline`/`health_history`/`fertilizer_logs` to do this.
All four are RLS-protected (migration 0003's `DIRECT_TENANT_TABLES`/
`JOIN_TENANT_TABLES`), and the public QR/passport request path has no
authenticated actor and therefore no `app.current_org_id` to scope with
(by design -- see migration 0003's own documented exemption for
`passports`: "the public tokenized read path ... is intentionally
unauthenticated and has no org context at all; access control is the
signed, time-scoped token itself"). Under real Postgres RLS, an unscoped
session's reads against those four tables would not error -- RLS
policies silently filter to zero rows -- so every public QR scan's
`health_status`/`growth_timeline`/`fertilizer_schedule` would quietly come
back null, a live-Postgres-shaped functional gap this sandbox's
Postgres-less test environment could not surface (caught by reasoning
through migration 0003's own table list against what `QRService.scan`
actually reads, while investigating this module's live-uvicorn-smoke-test
authentication bug -- see `app/api/deps.py`'s `get_qr_service`/
`get_public_passport_service` docstrings for that separate, related fix).

THE FIX, AND WHY IT IS NARROW. `Passport.public_token` verification
(HMAC-SHA256, constant-time compare, expiry-checked -- see
app/services/passport_service.py's module docstring) already IS this
request's authorization check; access control for the whole public
surface is deliberately "the signed, time-scoped token itself," per
migration 0003. Once `PassportService.get_passport_by_token` succeeds, the
caller has cryptographically proven the right to see exactly one plant's
public data -- `passport.plant_id`. This migration adds one additional
SELECT-only policy per table, keyed by a new session variable,
`app.qr_scan_plant_id`, that `QRService.scan` sets (via `set_config(...,
true)`, transaction-local, identical mechanism to migration 0003's
`app.current_org_id`) to that ONE verified `plant_id` immediately after
token verification, before issuing any of the four reads. This is not a
blanket RLS bypass: it does not grant org-wide access, does not touch
INSERT/UPDATE/DELETE (`FOR SELECT` only), and a row only becomes visible
under this policy if its own `id`/`plant_id` column exactly equals the
one plant a verified token already unlocked. `app.qr_scan_plant_id` is
never set from the internal, authenticated request path, so it has no
effect on -- and does not weaken -- the existing `app.current_org_id`
tenant-isolation policies from migration 0003, which remain fully in
force (Postgres OR-combines multiple permissive policies on the same
table; a row is visible if EITHER the tenant-isolation policy OR this new
one matches, which is exactly the intended "authenticated staff still see
their own org's rows; an anonymous QR scanner sees exactly the one row
their verified token unlocked" behavior).

`plants`/`growth_timeline`/`health_history` are already keyed on `id`/
`plant_id` respectively (migration 0003 already uses `plant_id` as
`JOIN_TENANT_TABLES`'s join column for the latter two). `fertilizer_logs`
has its own nullable `plant_id` column (app/models/digital_twin_records.py
-- migration 0003 chose `branch_id` as that table's *tenant*-isolation
join key, but the column this carve-out needs already exists independent
of that choice).
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

SESSION_VAR = "app.qr_scan_plant_id"

# (table, column) -- the column compared against the session variable.
# `plants` compares its own `id`; the other three compare their `plant_id` FK.
QR_SCAN_READABLE_TABLES = [
    ("plants", "id"),
    ("growth_timeline", "plant_id"),
    ("health_history", "plant_id"),
    ("fertilizer_logs", "plant_id"),
]


def _policy_sql(table: str, column: str) -> str:
    return f"""
    CREATE POLICY public_qr_scan_{table} ON {table}
    FOR SELECT
    USING (
        {column} = NULLIF(current_setting('{SESSION_VAR}', true), '')::uuid
    );
    """


def upgrade() -> None:
    # All four tables already have RLS enabled+forced by migration 0003
    # (ENABLE ROW LEVEL SECURITY / FORCE ROW LEVEL SECURITY) -- this
    # migration only adds one more permissive policy per table; Postgres
    # OR-combines permissive policies on the same table automatically, no
    # ALTER TABLE needed here.
    for table, column in QR_SCAN_READABLE_TABLES:
        op.execute(_policy_sql(table, column))


def downgrade() -> None:
    for table, _column in QR_SCAN_READABLE_TABLES:
        op.execute(f"DROP POLICY IF EXISTS public_qr_scan_{table} ON {table};")
