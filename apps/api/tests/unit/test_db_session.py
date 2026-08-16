"""
Regression test for a defect discovered while building Phase 6 Module 4:
`app/db/session.py`'s `get_db_session()` previously never called
`session.commit()`. SQLAlchemy's `AsyncSession` does not auto-commit on a
clean `async with` exit -- every write made through the real
`SqlAlchemy*Repository` classes (not the in-memory fakes every other test
in this suite uses) would have been silently rolled back at the end of
every request, in every module since Module 1. See
`get_db_session`'s docstring for the full writeup.

This is the one place in the test suite that exercises actual SQLAlchemy
commit/rollback behavior against a real engine rather than a hand-written
fake -- a fake repository can't catch "did the session actually commit",
since a fake never had a transaction to begin with. An in-memory SQLite
engine (via aiosqlite) is used instead of the app's real Postgres-only
models, since this test's whole point is control flow (does
`get_db_session` commit-on-success / rollback-on-exception), not schema
fidelity -- a real Postgres connection is still required to validate the
full production schema itself (the same disclosed, standing limitation as
every other "no live database reachable" note in this codebase).
"""
from __future__ import annotations

import pytest
from sqlalchemy import Integer, String, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

import app.db.session as db_session_module
from app.db.session import get_db_session

pytestmark = pytest.mark.unit


class _ScratchBase(DeclarativeBase):
    """A throwaway declarative base, deliberately separate from app.models.Base — this test only needs one simple, SQLite-portable table, not the full Postgres-specific production schema."""


class _Widget(_ScratchBase):
    __tablename__ = "widgets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50))


@pytest.fixture
async def sqlite_sessionmaker(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(_ScratchBase.metadata.create_all)

    sessionmaker = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    # get_db_session() references the module-level AsyncSessionLocal by
    # name at call time, so patching the module attribute (not just a
    # local variable) is what actually redirects it.
    monkeypatch.setattr(db_session_module, "AsyncSessionLocal", sessionmaker)

    yield sessionmaker
    await engine.dispose()


async def _row_count(sessionmaker) -> int:
    async with sessionmaker() as session:
        result = await session.execute(select(_Widget))
        return len(result.scalars().all())


async def test_get_db_session_commits_on_clean_completion(sqlite_sessionmaker):
    agen = get_db_session()
    session = await agen.__anext__()
    session.add(_Widget(id=1, name="committed-widget"))
    await session.flush()

    # Simulate the request completing without error -- drive the
    # generator to its natural end, exactly as FastAPI's dependency
    # machinery does when the route handler returns successfully.
    with pytest.raises(StopAsyncIteration):
        await agen.__anext__()

    assert await _row_count(sqlite_sessionmaker) == 1


async def test_get_db_session_rolls_back_on_exception(sqlite_sessionmaker):
    agen = get_db_session()
    session = await agen.__anext__()
    session.add(_Widget(id=1, name="doomed-widget"))
    await session.flush()

    class _SimulatedRouteError(Exception):
        pass

    # Simulate the request handler raising -- exactly what FastAPI does
    # when a route (or a dependency further down the chain) raises: the
    # exception is thrown back into this generator at its yield point.
    with pytest.raises(_SimulatedRouteError):
        await agen.athrow(_SimulatedRouteError("something failed mid-request"))

    assert await _row_count(sqlite_sessionmaker) == 0


async def test_get_db_session_yields_a_usable_session(sqlite_sessionmaker):
    agen = get_db_session()
    session = await agen.__anext__()

    result = await session.execute(select(_Widget))
    assert result.scalars().all() == []

    with pytest.raises(StopAsyncIteration):
        await agen.__anext__()
