"""
Structured (JSON in production, console-pretty in development) logging via
structlog, per docs/architecture/09-infrastructure.md §7 (Observability).
Every log line automatically carries the current request_id/org_id/user_id
from app/core/context.py, so logs are correlatable across a request's
whole call chain (API layer -> service -> repository) without passing a
logger instance around explicitly.
"""
from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.typing import EventDict, WrappedLogger

from app.core.context import current_org_id_var, current_user_id_var, request_id_var


def _add_request_context(logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
    request_id = request_id_var.get()
    if request_id is not None:
        event_dict["request_id"] = request_id
    org_id = current_org_id_var.get()
    if org_id is not None:
        event_dict["org_id"] = str(org_id)
    user_id = current_user_id_var.get()
    if user_id is not None:
        event_dict["user_id"] = str(user_id)
    return event_dict


def configure_logging(*, json_logs: bool, log_level: str = "INFO") -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=log_level)

    # Phase 6 Module 14 (Production Readiness) defect fix: explicit
    # `list[Any]` annotation (structlog's own processor stubs are
    # imprecise enough that annotating this `list[structlog.typing.
    # Processor]` still produced structural-mismatch errors against the
    # library's own built-in processors -- `Any` is the pragmatic,
    # correct-for-this-library choice, matching how structlog's own
    # documentation examples type this list). Without any annotation,
    # mypy inferred this list's element type from `_add_request_context`'s
    # (previously unannotated -- fixed above) signature and widened the
    # whole list to `list[object]`, which then made every consumer of
    # `shared_processors` below (the `processors=[*shared_processors, ...]`
    # call in `structlog.configure`) fail type-checking too. `mypy app`
    # caught this while validating this module; not something Module 14
    # itself introduced, but the first full `mypy app` pass this file had
    # apparently ever gotten.
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        _add_request_context,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    # Same list[Any]-widening rationale as `shared_processors` above --
    # `renderer`'s inferred `JSONRenderer | ConsoleRenderer` union type
    # still didn't structurally satisfy mypy's expected Processor
    # `Callable[...]` shape when placed in the `processors=[...]` list
    # below, for the same "structlog's own stubs are imprecise here"
    # reason.
    renderer: Any = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=[*shared_processors, structlog.processors.format_exc_info, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, log_level)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None):
    return structlog.get_logger(name)
