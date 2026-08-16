"""
The two response envelopes every endpoint in the system uses, per
docs/architecture/07-api-design.md §3 (Response Conventions). Declared
once here so every module's routes import the same shape instead of each
inventing its own — this is what lets the frontend (Phase 7) write one
error-handling code path for the entire API.
"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    code: str
    message: str
    context: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorDetail
    request_id: str | None = None


class PageMeta(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int


class Page(BaseModel, Generic[T]):
    """Standard paginated-list envelope every `GET /<resource>` list endpoint returns."""

    items: list[T]
    meta: PageMeta
