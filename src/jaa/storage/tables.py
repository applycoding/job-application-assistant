"""SQLModel table definitions."""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel


class DocumentRow(SQLModel, table=True):
    __tablename__ = "document"

    id: str = Field(primary_key=True)
    filename: str
    filename_key: str = Field(unique=True)
    media_type: str
    sha256: str = Field(unique=True)
    chunk_count: int
    created_at: datetime
    warnings_json: str = "[]"


class ChunkRow(SQLModel, table=True):
    __tablename__ = "chunk"

    id: str = Field(primary_key=True)
    doc_id: str = Field(foreign_key="document.id", index=True)
    line_no: int
    kind: str
    section: str
    text: str


class JobRow(SQLModel, table=True):
    __tablename__ = "job"

    id: str = Field(primary_key=True)
    payload_json: str
    created_at: datetime


class RunRow(SQLModel, table=True):
    __tablename__ = "run"

    seq: int | None = Field(default=None, primary_key=True)
    id: str = Field(unique=True, index=True)
    job_id: str = Field(foreign_key="job.id", index=True)
    parent_run_id: str | None = Field(default=None, foreign_key="run.id")
    payload_json: str
    corpus_version: str
    check_rules_version: str
    created_at: datetime


class RunCitationRow(SQLModel, table=True):
    __tablename__ = "run_citation"

    run_seq: int = Field(foreign_key="run.seq", primary_key=True)
    doc_id: str = Field(primary_key=True)
    chunk_id: str = Field(primary_key=True)
