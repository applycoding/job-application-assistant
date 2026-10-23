---
modules: src/jaa/storage/repo.py
checkpoint: uv run pytest tests/unit/test_repo.py tests/integration/test_concurrency.py
---

# SQLite storage

## Goal

Learn how documents, chunks, jobs, and runs are persisted in SQLite and accessed through a single `Repository` API.

## Files

- `src/jaa/storage/repo.py` implements upserts, job storage, run serialization, and corpus snapshots.
- `src/jaa/storage/db.py` creates the SQLAlchemy engine and applies schema migrations.
- `src/jaa/storage/tables.py` defines SQLModel rows (`DocumentRow`, `ChunkRow`, `JobRow`, `RunRow`, citations).

## Concepts

`upsert_document()` keys documents by a normalized `filename_key` and content `sha256`. Duplicate content under a different filename raises `DuplicateDocument` (HTTP 409 in the API).

Chunks are replaced atomically per document: old chunk rows for that `doc_id` are deleted before inserting the new set, with a guard on `MAX_CORPUS_CHUNKS`.

`RunData` bundles everything needed to replay a run: requirements, evidence, gaps, assembled drafts, truth report, and warnings. Saving a run stores JSON payloads and citation links for the UI export view.

## Code walkthrough

Start at `Repository.upsert_document`: filtered lines pass through `keep_line()` and the lexicon, then `chunk_document()` produces `Chunk` models persisted as `ChunkRow`. `corpus_snapshot(reference_date)` returns the version string plus all chunks eligible for retrieval on that date.

Concurrency tests exercise multiple writers against WAL mode; read `create_db_engine` for pragmas such as `foreign_keys=ON`.

## Checkpoint

Run: `uv run pytest tests/unit/test_repo.py tests/integration/test_concurrency.py`

## Exercise

After seeding, query `SELECT id, filename_key FROM document` in your DB file. Delete one document through the API or CLI and verify related chunks disappeared via foreign keys or explicit deletes in `repo.py`.
