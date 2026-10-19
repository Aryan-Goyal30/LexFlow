"""Database engine and session handling (synchronous SQLAlchemy 2)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from functools import lru_cache

from fastapi import Depends
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from lexflow.config import Settings, get_settings


@lru_cache
def engine_for(database_url: str) -> Engine:
    return create_engine(
        database_url,
        pool_pre_ping=True,
        # Keep case data out of error messages (and so out of any log).
        hide_parameters=True,
        # Fail fast instead of hanging when PostgreSQL is not reachable.
        connect_args={"connect_timeout": 3},
    )


def get_engine(settings: Settings = Depends(get_settings)) -> Engine:
    return engine_for(settings.database_url)


def get_session(engine: Engine = Depends(get_engine)) -> Iterator[Session]:
    """One session per request. Route code commits explicitly."""
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        yield session


IndependentSessions = Callable[[], AbstractContextManager[Session]]


def get_independent_sessions(engine: Engine = Depends(get_engine)) -> IndependentSessions:
    """Short-lived sessions that commit on their own, whatever the request does.

    Used for records that must survive a failed request: failed sign-in counters,
    lockouts and audit events. A ``with`` block commits when it ends normally
    and rolls back if it raises.
    """
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def scope() -> Iterator[Session]:
        with factory() as session:
            yield session
            session.commit()

    return scope
