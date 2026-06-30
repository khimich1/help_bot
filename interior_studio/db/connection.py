"""Подключение к SQLite и фабрика сессий."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from interior_studio.config import DATABASE_URL
from interior_studio.db.models import Base


def _sqlite_on_connect(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_db_engine(database_url: str | None = None) -> Engine:
    url = database_url or DATABASE_URL
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args)
    if url.startswith("sqlite"):
        event.listen(engine, "connect", _sqlite_on_connect)
    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


@contextmanager
def session_scope(
    engine: Engine | None = None,
    session_factory: sessionmaker[Session] | None = None,
) -> Generator[Session, None, None]:
    """Контекстный менеджер: commit при успехе, rollback при ошибке."""
    if session_factory is None:
        session_factory = create_session_factory(engine or create_db_engine())
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_schema(engine: Engine | None = None) -> None:
    eng = engine or create_db_engine()
    Base.metadata.create_all(eng)
