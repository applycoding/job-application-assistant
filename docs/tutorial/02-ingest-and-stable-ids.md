---
modules: src/jaa/ingest/loaders.py src/jaa/ingest/chunker.py
checkpoint: uv run pytest tests/unit/test_loaders.py tests/unit/test_chunker.py tests/unit/test_ids.py
---

# Ingest and stable chunk ids

## Goal

Turn uploaded CV files into classified lines, then into chunks with stable ids so retrieval and citations stay consistent across re-ingest of the same content.

## Files

- `src/jaa/ingest/loaders.py` reads PDF, DOCX, Markdown, and plain text with size and format guards.
- `src/jaa/ingest/chunker.py` splits lines, hashes chunk bodies, and computes `corpus_version`.
- `src/jaa/ids.py` assigns document ids (`Uuid4Factory` in production, `SeqIdFactory` in tests).
- `src/jaa/ingest/classify.py` and `normalize.py` label headings, bullets, and noise lines.

## Concepts

Each `RawLine` carries `line_no`, `text`, `kind`, and a `section` path (for example `Experience > Acme Corp`). Loaders raise `IngestError` for bad encodings or mismatched extensions, and `UploadTooLarge` when streaming exceeds `max_upload_mb`.

Chunk ids look like `{doc_id}:{16-char sha256 prefix}` where the hash input is `section + separator + text`. `ChunkIdCollision` fires if two different bodies share the same prefix, which protects citation integrity.

`corpus_version()` hashes ordered chunk metadata plus `RETRIEVAL_VERSION` and `CHECK_RULES_VERSION` so runs know when evidence pools changed.

## Code walkthrough

Follow `load_lines()` for your media type: PDF pages become lines, DOCX walks paragraphs and tables, Markdown respects `#` headings. Then `chunk_document()` expands overlong lines, optionally splits date ranges, and registers each chunk in a `seen` map inside `chunk_id()`.

## Checkpoint

Run: `uv run pytest tests/unit/test_loaders.py tests/unit/test_chunker.py tests/unit/test_ids.py`

## Exercise

Add a tiny `.md` resume snippet under `samples/` with a new employer section. Ingest it via CLI or API and print chunk ids from the repository; re-upload the same bytes and confirm ids are unchanged.

Read `jaa/limits.py` and list which constants bound PDF pages, DOCX zip entries, and total extracted characters for your file type.

Compare `Uuid4Factory` and `SeqIdFactory` in `ids.py` and state which one the CLI uses when ingesting a new file.
