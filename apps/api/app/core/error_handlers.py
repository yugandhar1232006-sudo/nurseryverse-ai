"""
Registers FastAPI exception handlers that translate every error path
(application-raised AppError, Pydantic/FastAPI's own RequestValidationError,
SQLAlchemy IntegrityError, and any truly unhandled exception) into the
single ErrorResponse envelope from app/core/responses.py. This is what
guarantees a client never has to special-case "what does an error look
like from this particular endpoint" -- it always looks like this.
"""
from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.context import request_id_var
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.core.responses import ErrorDetail, ErrorResponse

logger = get_logger(__name__)


def _envelope(request: Request, code: str, message: str, context: dict | None = None) -> dict:
    # Prefer request.state (survives past RequestContextMiddleware's own
    # finally-block reset of the contextvar on the exception path -- see
    # that middleware's dispatch() docstring comment); fall back to the
    # contextvar for the rare case a handler runs without request.state
    # populated (e.g. a raw ASGI-level failure before middleware ran).
    request_id = getattr(request.state, "request_id", None) or request_id_var.get()
    body = ErrorResponse(
        error=ErrorDetail(code=code, message=message, context=context or {}),
        request_id=request_id,
    )
    return jsonable_encoder(body)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        logger.info(
            "app_error",
            error_code=exc.error_code,
            detail=exc.detail,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(request, exc.error_code, exc.detail, exc.context),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope(
                request,
                "request_validation_error",
                "The request could not be validated.",
                {"errors": jsonable_encoder(exc.errors())},
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        # Catches FastAPI's own built-ins (404 for an unmatched route, etc.)
        # that never went through an AppError subclass.
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(request, "http_error", str(exc.detail)),
        )

    @app.exception_handler(IntegrityError)
    async def handle_integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
        # Backstop for the rare case a service layer lets a raw
        # IntegrityError escape instead of catching it and raising a
        # friendlier ConflictError first (see app/core/exceptions.py's
        # ConflictError docstring). Never leaks the raw SQL/constraint
        # name to the client -- that's logged, not returned.
        logger.warning("unhandled_integrity_error", detail=str(exc.orig), path=request.url.path)
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=_envelope(
                request, "conflict", "The request conflicts with existing data or a data rule."
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "unhandled_exception",
            exc_info=exc,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_envelope(request, "internal_error", "An unexpected error occurred."),
        )
