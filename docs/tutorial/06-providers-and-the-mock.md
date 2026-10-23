---
modules: src/jaa/providers/mock.py
checkpoint: uv run pytest tests/unit/test_outbound.py tests/unit/test_validate.py tests/unit/test_mock_provider.py
---

# Providers and the mock

## Goal

Understand the LLM provider interface, how outbound payloads are redacted, and how `MockProvider` simulates drafting and judging without network calls.

## Files

- `src/jaa/providers/mock.py` implements deterministic drafts and optional judge responses.
- `src/jaa/providers/base.py` defines `LLMProvider`, `CallBudget`, and structured output helpers.
- `src/jaa/providers/validate.py` enforces JSON schema and citation rules on model output.
- `src/jaa/privacy/outbound.py` builds `OutboundDraft` and `OutboundJudge` views.

## Concepts

Providers expose async `draft()` and `judge()` methods. The pipeline never sends raw SQLite rows to a model; it sends redacted evidence snippets and requirement text via `build_outbound_draft()`.

`MockProvider` ranks evidence with the same BM25 tokenization as retrieval, formats lead-in sentences from templates, and can inject `INJECTED_CLAIM` when `inject_unsupported=True` to test truth failures.

`validate_draft()` ensures every citation id exists in the outbound evidence list and that sentence structure matches `LLMDraftOut`.

## Code walkthrough

Trace `MockProvider.draft()`: tokenize the question plus must-have requirements, `_rank_pool()` orders chunks, `_unique_claim_text()` avoids duplicate claims, and each `SentenceOut` carries `citations` and `requirement_ids`.

For judge mode, read `MockProvider.judge()` and how `apply_judge()` in `truth/judge.py` merges verdicts back into `SentenceCheck` records.

## Checkpoint

Run: `uv run pytest tests/unit/test_outbound.py tests/unit/test_validate.py tests/unit/test_mock_provider.py`

## Exercise

Run a full mock pipeline integration test mentally: flip `inject_unsupported` off in a unit test and confirm the truth report has fewer unsupported sentences for the same fixture job.
