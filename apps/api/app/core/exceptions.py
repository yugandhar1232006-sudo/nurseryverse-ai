"""
Application exception hierarchy + the FastAPI handlers that turn every
raised exception into the single consistent error envelope defined in
app/core/responses.py (ErrorResponse). Every module from here on raises
one of these instead of a bare `HTTPException`, so the response shape
never varies by which module produced the error — a frontend integration
(Phase 7) only ever has to parse one error format.

Design: a small, closed hierarchy of *categories* (not one exception per
business rule) — RESTRICT-violation-style conflicts, not-found, validation,
permission, and auth failures cover every error case in the architecture
docs' API design (docs/architecture/07-api-design.md §4, Error Handling).
Module-specific detail goes in the `detail`/`context` fields, not in a
proliferation of exception subclasses future engineers would have to
memorize.
"""
from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base class for every application-raised error. Never raised directly."""

    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(self, detail: str, *, context: dict[str, Any] | None = None) -> None:
        self.detail = detail
        self.context = context or {}
        super().__init__(detail)


class NotFoundError(AppError):
    """A requested entity does not exist (or is invisible to this tenant)."""

    status_code = 404
    error_code = "not_found"


class ValidationError(AppError):
    """
    Request is well-formed JSON/schema but fails a business rule Pydantic
    can't express alone (e.g. "received_quantity <= ordered_quantity"
    checked pre-flight for a friendlier error than the raw CHECK
    constraint violation would give).
    """

    status_code = 422
    error_code = "validation_error"


class ConflictError(AppError):
    """
    A uniqueness or referential-integrity rule was violated in a way the
    caller can act on (duplicate botanical name, deleting a still-
    referenced supplier). This is the friendly error the Phase 5 readiness
    review's §1 Cascade Rules section promised ahead of the raw
    IntegrityError from an ON DELETE RESTRICT constraint.
    """

    status_code = 409
    error_code = "conflict"


class PermissionDeniedError(AppError):
    """Authenticated, but lacks the required `<module>:<action>` permission."""

    status_code = 403
    error_code = "permission_denied"


class AuthenticationError(AppError):
    """Missing, expired, or invalid credentials."""

    status_code = 401
    error_code = "authentication_error"


class RateLimitError(AppError):
    status_code = 429
    error_code = "rate_limited"


class ModelUnavailableError(AppError):
    """
    Added by Phase 6 Module 10 (AI Platform). An AI backend this request
    needed isn't reachable or isn't configured -- a missing/unloadable
    model artifact (`ModelRegistry.get()`, docs/architecture/02-low-level-
    design.md's "Module: AI Predictions" §Error handling), or the
    Anthropic Claude API being unreachable/erroring/unconfigured for the
    AI Assistant (same section, "Module: AI Assistant" §Error handling:
    "LLM API failure surfaces as an inline chat error with retry, never
    blocks the rest of the app"). Deliberately its own category rather
    than reusing `ConflictError`/`ValidationError`: this is neither a bad
    request nor a data-integrity problem, it is a dependency the server
    itself is currently missing -- 503, not 409/422/500, matching this
    codebase's existing `/readyz` precedent for "a backend dependency is
    unreachable" (app/api/routes/health.py).
    """

    status_code = 503
    error_code = "model_unavailable"
