---
modules: src/jaa/retrieval/service.py
checkpoint: uv run pytest tests/unit/test_eligibility.py tests/unit/test_bm25.py tests/unit/test_retrieval_service.py
---

# Retrieval

## Goal

See how JAA selects CV evidence for each job requirement using eligibility rules first, then BM25 ranking within a bounded pool.

## Files

- `src/jaa/retrieval/service.py` exposes `retrieve_for_job()`.
- `src/jaa/retrieval/eligibility.py` decides which requirement terms appear in a chunk.
- `src/jaa/retrieval/bm25.py` scores chunks for a tokenized query.
- `src/jaa/retrieval/tokenize.py` normalizes text for matching.

## Concepts

Retrieval is not embedding-based in this project: it is transparent lexical BM25 over chunk text, which makes tests deterministic and cheap.

For each requirement, chunks must pass `eligible()` before they enter the candidate list. The service then builds a query from requirement text plus declared skills, ranks eligible chunks, and picks up to `K_PER_REQ` items while respecting `POOL_MAX` globally.

`Gap` records mark requirements with no eligible chunk or missing individual terms, which the UI and outbound draft use to warn the user.

## Code walkthrough

In `retrieve_for_job()`, note the two-level structure: per-requirement scoring, then aggregation into `EvidenceItem` rows with matched terms. `_compute_gaps()` compares required terms against the union of matched terms in the pool.

Open `BM25Ranker` to see how document frequency is computed across the in-memory chunk list for each run snapshot.

## Checkpoint

Run: `uv run pytest tests/unit/test_eligibility.py tests/unit/test_bm25.py tests/unit/test_retrieval_service.py`

## Exercise

Write a short test that builds two chunks, one mentioning "Kubernetes" and one not. Parse a job requiring Kubernetes and assert the gap list is empty only when the matching chunk is present.
