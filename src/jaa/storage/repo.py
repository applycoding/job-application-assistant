"""Repository over SQLite."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from jaa.clock import Clock
from jaa.ids import IdFactory
from jaa.ingest.chunker import chunk_document, corpus_version
from jaa.ingest.classify import keep_line
from jaa.ingest.loaders import IngestError
from jaa.ingest.normalize import filename_key
from jaa.limits import MAX_CORPUS_CHUNKS
from jaa.models import (
    Chunk,
    Document,
    Drafts,
    EvidenceItem,
    Gap,
    JobPost,
    MediaType,
    RawLine,
    Requirement,
    Run,
    TruthReport,
)
from jaa.storage.db import create_db_engine
from jaa.storage.tables import ChunkRow, DocumentRow, JobRow, RunCitationRow, RunRow
from jaa.truth.lexicon import SkillLexicon


class DuplicateDocument(IngestError):
    """Same sha256 already stored under a different filename key (409)."""


@dataclass
class RunData:
    job_id: str
    parent_run_id: str | None
    provider: str
    model: str
    judge_model: str | None
    judge_enabled: bool
    corpus_version: str
    check_rules_version: str
    requirements: list[Requirement]
    evidence: list[EvidenceItem]
    gaps: list[Gap]
    drafts: Drafts
    report: TruthReport
    warnings: list[str]


class Repository:
    def __init__(
        self,
        engine: Engine,
        clock: Clock,
        ids: IdFactory,
        lexicon: SkillLexicon,
    ) -> None:
        self._engine = engine
        self._clock = clock
        self._ids = ids
        self._lexicon = lexicon

    @classmethod
    def open(
        cls,
        db_path: str | Path,
        clock: Clock,
        ids: IdFactory,
        lexicon: SkillLexicon,
    ) -> Repository:
        from pathlib import Path as PathCls

        return cls(create_db_engine(PathCls(db_path)), clock, ids, lexicon)

    def upsert_document(
        self,
        filename: str,
        media_type: MediaType,
        sha256: str,
        lines: list[RawLine],
        warnings: list[str],
    ) -> Document:
        fkey = filename_key(filename)
        filtered = [ln for ln in lines if keep_line(ln, self._lexicon)]
        with Session(self._engine) as session:
            existing_key = session.exec(
                select(DocumentRow).where(DocumentRow.filename_key == fkey)
            ).first()
            existing_sha = session.exec(
                select(DocumentRow).where(DocumentRow.sha256 == sha256)
            ).first()

            if existing_key is not None:
                doc_id = existing_key.id
                if existing_sha is not None and existing_sha.id != doc_id:
                    raise DuplicateDocument(
                        "Document with this content already exists under another name"
                    )
                old_chunks = session.exec(
                    select(ChunkRow).where(ChunkRow.doc_id == doc_id)
                ).all()
                other_count = len(
                    [c for c in session.exec(select(ChunkRow)).all() if c.doc_id != doc_id]
                )
                new_chunks = chunk_document(doc_id, filtered)
                if other_count + len(new_chunks) > MAX_CORPUS_CHUNKS:
                    raise IngestError(f"Corpus exceeds {MAX_CORPUS_CHUNKS} chunks")
                for row in old_chunks:
                    session.delete(row)
                self._insert_chunks(session, new_chunks)
                existing_key.filename = filename
                existing_key.media_type = media_type
                existing_key.sha256 = sha256
                existing_key.chunk_count = len(new_chunks)
                existing_key.warnings_json = json.dumps(warnings)
                session.add(existing_key)
                session.commit()
                return self._document_from_row(existing_key)

            if existing_sha is not None:
                raise DuplicateDocument(
                    "Document with this content already exists under another name"
                )

            other_chunks = len(session.exec(select(ChunkRow)).all())
            doc_id = self._ids.new_doc_id()
            new_chunks = chunk_document(doc_id, filtered)
            if other_chunks + len(new_chunks) > MAX_CORPUS_CHUNKS:
                raise IngestError(f"Corpus exceeds {MAX_CORPUS_CHUNKS} chunks")
            created = self._clock.now()
            row = DocumentRow(
                id=doc_id,
                filename=filename,
                filename_key=fkey,
                media_type=media_type,
                sha256=sha256,
                chunk_count=len(new_chunks),
                created_at=created,
                warnings_json=json.dumps(warnings),
            )
            session.add(row)
            self._insert_chunks(session, new_chunks)
            session.commit()
            return self._document_from_row(row)

    def _insert_chunks(self, session: Session, chunks: list[Chunk]) -> None:
        for ch in chunks:
            session.add(
                ChunkRow(
                    id=ch.id,
                    doc_id=ch.doc_id,
                    line_no=ch.line_no,
                    kind=ch.kind,
                    section=ch.section,
                    text=ch.text,
                )
            )

    def list_documents(self) -> list[Document]:
        with Session(self._engine) as session:
            rows = session.exec(select(DocumentRow).order_by(DocumentRow.created_at)).all()
            return [self._document_from_row(r) for r in rows]

    def get_chunks(
        self,
        doc_id: str | None = None,
        *,
        retrievable_only: bool = False,
    ) -> list[Chunk]:
        with Session(self._engine) as session:
            stmt = select(ChunkRow)
            if doc_id is not None:
                stmt = stmt.where(ChunkRow.doc_id == doc_id)
            rows = session.exec(stmt.order_by(ChunkRow.id)).all()
            chunks = [self._chunk_from_row(r) for r in rows]
            if retrievable_only:
                chunks = [c for c in chunks if c.kind not in ("heading", "contact")]
            return chunks

    def corpus_snapshot(self, reference_date: date) -> tuple[str, list[Chunk]]:
        with Session(self._engine) as session:
            rows = session.exec(select(ChunkRow).order_by(ChunkRow.id)).all()
            chunks = [self._chunk_from_row(r) for r in rows]
            retrievable = [c for c in chunks if c.kind not in ("heading", "contact")]
            version = corpus_version(
                retrievable,
                lexicon_version=self._lexicon.version,
                reference_date=reference_date,
            )
            return version, retrievable

    def delete_document(self, doc_id: str, *, delete_runs: bool = False) -> int:
        deleted_runs = 0
        with Session(self._engine) as session:
            doc = session.get(DocumentRow, doc_id)
            if doc is None:
                raise KeyError(doc_id)
            if delete_runs:
                cite_rows = session.exec(
                    select(RunCitationRow).where(RunCitationRow.doc_id == doc_id)
                ).all()
                run_seqs = {r.run_seq for r in cite_rows}
                for seq in run_seqs:
                    run = session.exec(select(RunRow).where(RunRow.seq == seq)).first()
                    if run is not None:
                        cites = session.exec(
                            select(RunCitationRow).where(RunCitationRow.run_seq == seq)
                        ).all()
                        for c in cites:
                            session.delete(c)
                        session.delete(run)
                        deleted_runs += 1
            chunks = session.exec(select(ChunkRow).where(ChunkRow.doc_id == doc_id)).all()
            for ch in chunks:
                session.delete(ch)
            session.delete(doc)
            session.commit()
        return deleted_runs

    def save_job(self, job: JobPost) -> JobPost:
        with Session(self._engine) as session:
            existing = session.get(JobRow, job.id)
            payload = job.model_dump_json()
            if existing is not None:
                existing.payload_json = payload
                existing.created_at = job.created_at
                session.add(existing)
            else:
                session.add(
                    JobRow(
                        id=job.id,
                        payload_json=payload,
                        created_at=job.created_at,
                    )
                )
            session.commit()
        return job

    def get_job(self, job_id: str) -> JobPost:
        with Session(self._engine) as session:
            row = session.get(JobRow, job_id)
            if row is None:
                raise KeyError(job_id)
            return JobPost.model_validate_json(row.payload_json)

    def list_jobs(self) -> list[JobPost]:
        with Session(self._engine) as session:
            rows = session.exec(select(JobRow).order_by(JobRow.created_at)).all()
            return [JobPost.model_validate_json(r.payload_json) for r in rows]

    def insert_run(self, run: RunData) -> Run:
        with Session(self._engine) as session:
            created = self._clock.now()
            row = RunRow(
                seq=None,
                id=f"__pending__{uuid.uuid4().hex}",
                job_id=run.job_id,
                parent_run_id=run.parent_run_id,
                payload_json="{}",
                corpus_version=run.corpus_version,
                check_rules_version=run.check_rules_version,
                created_at=created,
            )
            session.add(row)
            session.flush()
            seq = row.seq
            if seq is None:
                raise RuntimeError("Failed to allocate run sequence")
            run_id = f"run-{seq:04d}"
            run_model = Run(
                id=run_id,
                job_id=run.job_id,
                parent_run_id=run.parent_run_id,
                created_at=created,
                provider=run.provider,
                model=run.model,
                judge_model=run.judge_model,
                judge_enabled=run.judge_enabled,
                corpus_version=run.corpus_version,
                check_rules_version=run.check_rules_version,
                requirements=run.requirements,
                evidence=run.evidence,
                gaps=run.gaps,
                drafts=run.drafts,
                report=run.report,
                warnings=run.warnings,
            )
            row.id = run_id
            row.payload_json = run_model.model_dump_json()
            session.add(row)
            self._index_run_citations(session, seq, run_model)
            session.commit()
            return run_model

    def _index_run_citations(self, session: Session, seq: int, run: Run) -> None:
        cited: set[tuple[str, str]] = set()
        for answer in run.drafts.answers:
            for sentence in answer.sentences:
                for cid in sentence.citations:
                    chunk_row = session.get(ChunkRow, cid)
                    if chunk_row is not None:
                        cited.add((chunk_row.doc_id, cid))
        for sentence in run.drafts.cover_note.sentences:
            for cid in sentence.citations:
                chunk_row = session.get(ChunkRow, cid)
                if chunk_row is not None:
                    cited.add((chunk_row.doc_id, cid))
        for doc_id, chunk_id in cited:
            session.add(RunCitationRow(run_seq=seq, doc_id=doc_id, chunk_id=chunk_id))

    def get_run(self, run_id: str) -> Run:
        with Session(self._engine) as session:
            row = session.exec(select(RunRow).where(RunRow.id == run_id)).first()
            if row is None:
                raise KeyError(run_id)
            return Run.model_validate_json(row.payload_json)

    def list_runs(self, job_id: str) -> list[Run]:
        with Session(self._engine) as session:
            rows = session.exec(
                select(RunRow).where(RunRow.job_id == job_id).order_by(RunRow.seq)
            ).all()
            return [Run.model_validate_json(r.payload_json) for r in rows]

    def delete_all(self) -> None:
        with Session(self._engine) as session:
            session.exec(text("DELETE FROM run_citation"))
            session.exec(text("DELETE FROM run"))
            session.exec(text("DELETE FROM chunk"))
            session.exec(text("DELETE FROM document"))
            session.exec(text("DELETE FROM job"))
            session.commit()
        with self._engine.connect() as conn:
            conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
            conn.execute(text("VACUUM"))
            conn.commit()

    @staticmethod
    def _document_from_row(row: DocumentRow) -> Document:
        return Document(
            id=row.id,
            filename=row.filename,
            filename_key=row.filename_key,
            media_type=row.media_type,  # type: ignore[arg-type]
            sha256=row.sha256,
            chunk_count=row.chunk_count,
            created_at=row.created_at,
            warnings=json.loads(row.warnings_json),
        )

    @staticmethod
    def _chunk_from_row(row: ChunkRow) -> Chunk:
        return Chunk(
            id=row.id,
            doc_id=row.doc_id,
            line_no=row.line_no,
            kind=row.kind,  # type: ignore[arg-type]
            section=row.section,
            text=row.text,
        )
