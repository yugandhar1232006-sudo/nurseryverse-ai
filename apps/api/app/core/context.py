"""
Request-scoped context, propagated via `contextvars` rather than
FastAPI's `request.state` so it's readable from anywhere in the call
stack (repositories, services, the structured logger) without threading
the `Request` object through every function signature.

Populated by `app/core/middleware.py` on every request:
- `request_id_var` — set immediately, before auth, for correlating logs
  even on requests that fail authentication.
- `current_org_id_var` / `current_user_id_var` / `current_branch_ids_var`
  — set by the Authentication/Authorization dependencies (Module 2/3,
  not this module), once the JWT is verified. Declared here now so every
  later module imports the same context object instead of each inventing
  its own.

`current_org_id_var` is also what Module 3's DB session dependency uses
to issue `SET LOCAL app.current_org_id = ...` at the start of each
request's transaction — the session variable the RLS policies
(migrations/versions/0003_row_level_security.py) key against. This file
only defines the contextvars; wiring them into the session is Module 3's
job (Authorization), since it depends on auth existing first.
"""
from __future__ import annotations

import uuid
from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
current_user_id_var: ContextVar[uuid.UUID | None] = ContextVar("current_user_id", default=None)
current_org_id_var: ContextVar[uuid.UUID | None] = ContextVar("current_org_id", default=None)
current_branch_ids_var: ContextVar[tuple[uuid.UUID, ...] | None] = ContextVar(
    "current_branch_ids", default=None
)


def new_request_id() -> str:
    return uuid.uuid4().hex
