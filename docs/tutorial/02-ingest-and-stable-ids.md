---
modules: src/jaa/ingest/loaders.py src/jaa/ingest/chunker.py
checkpoint: uv run pytest tests/unit/test_loaders.py tests/unit/test_chunker.py tests/unit/test_ids.py
---

# Ingest

## Goal

Learn ingest in the job-application-assistant codebase.

## Files

See front matter `modules`.

## Concepts

This chapter maps to the final implementation (no historical stages).

## Code walkthrough

Walk through the listed modules in `src/jaa`.

## Checkpoint

Run: `uv run pytest tests/unit/test_loaders.py tests/unit/test_chunker.py tests/unit/test_ids.py`

## Exercise

Extend tests or add a small feature, then re-run the checkpoint.
