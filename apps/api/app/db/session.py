"""
Async engine/session factory. Connection pooling parameters per
docs/architecture/09-infrastructure.md §5 (PgBouncer sits in front of this
in production; the pool_size here is the application-side pool talking to
PgBouncer, not directly to Postgres).
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(
    settings.sqlalchemy_database_uri_async,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,
    echo=settings.APP_DEBUG,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine, expire_on_commit=False, autoflush=False
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency — yields a session, always closed after the
    request. Commits on a clean request, rolls back on any raised
    exception (an `AppError`, an unhandled bug, whatever) so a failed
    request can never leave a partial write behind.

    Defect fix (discovered while building Phase 6 Module 4): this
    function previously only did `async with AsyncSessionLocal() as
    session: yield session`, with no `commit()` anywhere. SQLAlchemy's
    `AsyncSession` does not auto-commit on a clean context-manager exit —
    `close()` implicitly rolls back whatever wasn't explicitly committed.
    Every write since Module 1 (Module 2's login/token/lockout state,
    Module 3's authorization denials, anything using the real
    `SqlAlchemy*Repository` classes against a real database) would have
    been silently discarded at the end of every request. This never
    surfaced in this sandbox's test suite because every unit/integration
    test runs against in-memory fakes (tests/fakes/repositories.py), never
    the real repositories against a real Postgres connection where
    commit-vs-rollback is actually observable — exactly the kind of gap
    the "no live database reachable" limitation, disclosed in every
    module's doc, was always going to eventually hide. Fixed here,
    regression-tested in
    tests/unit/test_db_session.py (a real, in-memory SQLite engine, the
    one place in this codebase where testing *actual* commit/rollback
    behavior against a real SQLAlchemy engine — not a hand-written fake —
    is both feasible offline and the right tool for the job).
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
