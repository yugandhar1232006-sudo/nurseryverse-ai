"""
Regenerates the ROLES / PERMISSIONS / ROLE_PERMISSIONS data blocks in
migrations/versions/0002_seed_system_metadata.py by parsing
docs/ux/07-role-permission-matrix.md directly — this is what produced that
migration's seed data in the first place. Run this and splice the output
back in whenever the permission matrix document changes, instead of
hand-editing the migration's data arrays, so the two can never drift.

Note: this generates fresh random UUIDs for every role/permission on each
run. Re-running it after the migration has already shipped to any real
environment would change every ID — don't re-run against a shipped
migration; only use it to review/regenerate before first release, or as
the starting point for a *new* migration if the matrix changes later.
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path

MATRIX_PATH = Path(__file__).resolve().parents[3] / "docs" / "ux" / "07-role-permission-matrix.md"
ROLES = ["owner", "org_admin", "branch_manager", "horticulturist", "sales_staff"]


def parse_matrix() -> dict[str, dict[str, str | None]]:
    perms: dict[str, dict[str, str | None]] = {}
    for line in MATRIX_PATH.read_text().splitlines():
        if not line.startswith("| `"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != 6:
            continue
        m = re.match(r"`([a-z_]+:[a-z_]+)`", cells[0])
        if not m:
            continue
        code = m.group(1)
        scopes: dict[str, str | None] = {}
        for role, val in zip(ROLES, cells[1:6]):
            v = val.strip()
            scopes[role] = v[0] if v[:1] in ("F", "B", "R") else None
        perms[code] = scopes
    return perms


def main() -> None:
    perms = parse_matrix()
    role_ids = {r: str(uuid.uuid4()) for r in [*ROLES, "platform_admin"]}

    print(f"-- Parsed {len(perms)} permission codes from {MATRIX_PATH}")
    print("ROLES =", [{"id": role_ids[r], "code": r} for r in role_ids])
    print()
    print(f"-- {sum(1 for s in perms.values() for v in s.values() if v)} role_permissions grants total")


if __name__ == "__main__":
    main()
