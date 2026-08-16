"""
Application factory. `create_app()` rather than a bare module-level `app`
so tests can construct fresh instances with overridden settings/dependencies
(tests/conftest.py) without import-order side effects -- important once
Modules 2+ add startup-time work (e.g. verifying the JWT keys are present).
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_v1_router, root_router
from app.core.config import Settings, get_settings
from app.core.error_handlers import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.cache import InMemoryCache
from app.core.middleware import RequestContextMiddleware
from app.core.rate_limit import InMemoryRateLimiter
from app.db.session import engine
from app.notifications.hub import InMemoryNotificationHub

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("app_startup", env=app.state.settings.APP_ENV)
    await _try_upgrade_to_redis_rate_limiter(app)
    await _try_upgrade_to_redis_cache(app)
    yield
    logger.info("app_shutdown")
    await engine.dispose()


async def _try_upgrade_to_redis_rate_limiter(app: FastAPI) -> None:
    """
    `app.state.rate_limiter` starts as an InMemoryRateLimiter (set in
    create_app, before lifespan even runs, so it's available immediately
    for ASGI test transports that never trigger lifespan events at all).
    On real startup, attempt a genuine Redis connection and swap in
    RedisRateLimiter if it succeeds -- required for correct rate limiting
    across multiple API processes/replicas, which InMemoryRateLimiter
    cannot provide. Falls back to the in-memory limiter with a warning
    (not a crash) if Redis is unreachable, since a missing rate limiter
    backend should degrade the feature, not take down the whole API --
    the same reasoning /readyz already applies to the database.
    """
    settings: Settings = app.state.settings
    try:
        import redis.asyncio as redis_asyncio

        client = redis_asyncio.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        await client.ping()
    except Exception as exc:  # noqa: BLE001 -- any Redis failure means "stay on the in-memory fallback"
        logger.warning("redis_unreachable_using_in_memory_rate_limiter", error=str(exc))
        return

    from app.core.rate_limit import RedisRateLimiter

    app.state.rate_limiter = RedisRateLimiter(client)
    logger.info("redis_rate_limiter_active")


async def _try_upgrade_to_redis_cache(app: FastAPI) -> None:
    """
    Same upgrade-with-graceful-fallback pattern as
    `_try_upgrade_to_redis_rate_limiter`, for Module 3's permission cache
    (app/core/cache.py). `app.state.cache` starts as an `InMemoryCache`
    (set in `create_app`, before lifespan) so ASGI test transports that
    skip lifespan events still get a working, per-app-instance cache; a
    real multi-process deployment needs Redis for cache coherency across
    replicas (an in-memory cache on replica A wouldn't see replica B's
    `invalidate_user` call), so this swaps one in when reachable and logs
    a warning rather than crashing when it isn't — a missing cache
    backend should degrade permission-resolution to "always hits
    Postgres", not take down the API.
    """
    settings: Settings = app.state.settings
    try:
        import redis.asyncio as redis_asyncio

        client = redis_asyncio.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        await client.ping()
    except Exception as exc:  # noqa: BLE001 -- any Redis failure means "stay on the in-memory fallback"
        logger.warning("redis_unreachable_using_in_memory_cache", error=str(exc))
        return

    from app.core.cache import RedisCache

    app.state.cache = RedisCache(client)
    logger.info("redis_cache_active")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(json_logs=settings.is_production, log_level="DEBUG" if settings.APP_DEBUG else "INFO")

    app = FastAPI(
        title=settings.APP_NAME,
        description=(
            "NurseryVerse AI — AI-Powered Plant Digital Twin & Nursery "
            "Intelligence Platform. Production API; see "
            "docs/architecture/07-api-design.md for the full design."
        ),
        version="0.1.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = settings
    # Set immediately (not just in lifespan) so it's present even for ASGI
    # transports that skip lifespan events entirely (httpx's ASGITransport
    # in tests/conftest.py, notably) -- every app instance gets its own
    # limiter, which is also what keeps tests from bleeding rate-limit
    # state into each other the way one shared module-level singleton
    # would (see app/api/deps.py's get_rate_limiter docstring).
    app.state.rate_limiter = InMemoryRateLimiter()
    # Same reasoning as app.state.rate_limiter above, for Module 3's
    # permission cache (app/api/deps.py's get_cache).
    app.state.cache = InMemoryCache()
    # Module 11 (Notifications): the WebSocket connection registry. Same
    # in-memory-first shape as rate_limiter/cache above -- correct for
    # this project's single-process deployment; a multi-replica deployment
    # would need a Redis pub/sub-backed hub to fan a push out to whichever
    # replica holds a given user's live socket, which is a disclosed,
    # not-yet-built upgrade path (see app/notifications/hub.py's own
    # module docstring), exactly like rate_limiter/cache's own Redis
    # upgrade paths above.
    app.state.notification_hub = InMemoryNotificationHub()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)

    app.include_router(root_router)
    app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_app()
