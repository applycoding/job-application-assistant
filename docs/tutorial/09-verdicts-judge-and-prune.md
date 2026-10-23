---
modules: src/jaa/truth/prune.py
checkpoint: uv run pytest tests/unit/test_verdict.py tests/unit/test_judge.py tests/unit/test_prune.py
---

# Verdicts, judge, and prune

## Goal

Combine deterministic statuses with an optional LLM judge, then remove flagged sentences while keeping framing lines and surfacing warnings.

## Files

- `src/jaa/truth/prune.py` implements `prune_flagged()`.
- `src/jaa/truth/judge.py` calls `provider.judge()` for eligible sentences.
- `src/jaa/truth/report.py` orchestrates checks and judge passes into a `TruthReport`.
- `src/jaa/truth/verdict.py` centralizes status transitions when judge or failures apply.

## Concepts

Deterministic checks run for every claim. Sentences that pass and have no failures may be sent to the judge when `judge_enabled` is true and the provider supports `judge()`.

Judge failures append a `CheckFailure` with check name `judge` and flip status to unsupported. If the provider raises `JudgeUnavailable`, checks are marked accordingly without crashing the run.

`prune_flagged()` drops sentences whose ids appear in `report.flagged_ids` but never removes cover-note framing lines. Empty answers after pruning produce warnings so users know to write manually.

## Code walkthrough

Open `run_truth_check()` in `report.py` to see ordering: build checks per sentence, optionally `apply_judge()`, then aggregate flagged ids for the UI prune button.

In `prune_flagged()`, notice how cover claims can all be removed while framing remains, triggering "add manually" warnings.

## Checkpoint

Run: `uv run pytest tests/unit/test_verdict.py tests/unit/test_judge.py tests/unit/test_prune.py`

## Exercise

Simulate a run where one answer sentence fails deterministic checks and another fails only the judge. After `prune_flagged()`, count remaining sentences per answer and match them to your expectations.
