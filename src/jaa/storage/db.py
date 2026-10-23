"""SQLite engine setup with required pragmas."""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from jaa.storage.tables import ChunkRow, DocumentRow, JobRow, RunCitationRow, RunRow


def _set_sqlite_pragma(dbapi_conn: object, _connection_record: object) -> None:
    cursor = dbapi_conn.cursor()  # type: ignore[attr-defined]
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


def create_db_engine(db_path: Path) -> Engine:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    event.listen(engine, "connect", _set_sqlite_pragma)
    SQLModel.metadata.create_all(
        engine,
        tables=[
            DocumentRow.__table__,  # type: ignore[attr-defined]
            ChunkRow.__table__,  # type: ignore[attr-defined]
            JobRow.__table__,  # type: ignore[attr-defined]
            RunRow.__table__,  # type: ignore[attr-defined]
            RunCitationRow.__table__,  # type: ignore[attr-defined]
        ],
    )
    if db_path.exists():
        os.chmod(db_path, 0o600)
    return engine


@contextmanager
def session_scope(engine: Engine) -> Generator[Session]:
    with Session(engine) as session:
        yield session
