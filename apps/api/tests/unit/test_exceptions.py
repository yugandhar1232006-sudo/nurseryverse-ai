"""Unit tests for the AppError hierarchy (app/core/exceptions.py)."""
from __future__ import annotations

import pytest

from app.core.exceptions import (
    AppError,
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ValidationError,
)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("exc_cls", "expected_status", "expected_code"),
    [
        (NotFoundError, 404, "not_found"),
        (ValidationError, 422, "validation_error"),
        (ConflictError, 409, "conflict"),
        (PermissionDeniedError, 403, "permission_denied"),
        (AuthenticationError, 401, "authentication_error"),
        (RateLimitError, 429, "rate_limited"),
    ],
)
def test_error_status_and_code(exc_cls, expected_status, expected_code):
    exc = exc_cls("something went wrong")
    assert exc.status_code == expected_status
    assert exc.error_code == expected_code
    assert exc.detail == "something went wrong"
    assert exc.context == {}


@pytest.mark.unit
def test_error_carries_context():
    exc = NotFoundError("plant not found", context={"plant_id": "abc-123"})
    assert exc.context == {"plant_id": "abc-123"}


@pytest.mark.unit
def test_every_subclass_is_an_app_error():
    for exc_cls in (
        NotFoundError,
        ValidationError,
        ConflictError,
        PermissionDeniedError,
        AuthenticationError,
        RateLimitError,
    ):
        assert issubclass(exc_cls, AppError)
