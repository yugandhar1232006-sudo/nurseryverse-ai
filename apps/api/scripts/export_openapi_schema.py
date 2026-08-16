"""
Dumps the live FastAPI app's OpenAPI schema to JSON so the frontend
(apps/web) can regenerate its TypeScript API types from it via
`npm run generate:api-types` (see apps/web/package.json and
apps/web/lib/api/generated/). This is the one and only source the
frontend's request/response types come from -- per the Phase 7 kickoff's
"do not manually duplicate API types when generated types can be used"
requirement, nobody hand-writes a TS interface for a backend schema.

Usage (from apps/api/):
    python3 scripts/export_openapi_schema.py [output_path]

Defaults to writing ../web/lib/api/generated/openapi.json (i.e. directly
into the frontend's own generated/ directory) so the two-step refresh is
just:
    python3 apps/api/scripts/export_openapi_schema.py
    (cd apps/web && npm run generate:api-types)

Re-run both steps any time a backend route/schema changes -- this is a
plain data dump against the real, current `app.openapi()` output, not a
hand-maintained spec that can drift from the code.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, ".")


def main() -> None:
    from app.main import create_app

    app = create_app()
    schema = app.openapi()

    if len(sys.argv) > 1:
        output_path = Path(sys.argv[1])
    else:
        output_path = Path(__file__).resolve().parents[2] / "web" / "lib" / "api" / "generated" / "openapi.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(schema, indent=2))
    print(f"Wrote OpenAPI schema ({len(schema.get('paths', {}))} paths, "
          f"{len(schema.get('components', {}).get('schemas', {}))} component schemas) to {output_path}")


if __name__ == "__main__":
    main()
