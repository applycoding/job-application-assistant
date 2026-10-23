---
modules: src/jaa/generation/pipeline.py
checkpoint: uv run pytest tests/unit/test_prompts.py tests/integration/test_pipeline.py
---

# Generation, citations, and explanations

## Goal

Follow a run from corpus snapshot through LLM drafting, assembly into user-facing drafts, and optional pruning after truth checks.

## Files

- `src/jaa/generation/pipeline.py` defines `create_run()`, `prune_run()`, and `Deps`.
- `src/jaa/generation/assemble.py` turns `LLMDraftOut` into `Drafts` with sentence ids and cover-note framing.
- `src/jaa/generation/templates.py` and `explain.py` supply static framing lines and rationale helpers.
- `src/jaa/providers/prompts.py` holds system prompts for real providers (mock uses code paths instead).

## Concepts

`create_run()` loads chunks via `repo.corpus_snapshot()`, calls `retrieve_for_job()`, builds outbound data, awaits `provider.draft()`, then `assemble_drafts()`. Truth checking runs immediately via `run_truth_check()` with an optional judge.

`assemble_drafts()` assigns stable sentence ids like `Q1.S1`, drops unknown requirement ids with warnings, and prepends cover-note framing sentences that are marked `kind="framing"` so checks skip them.

`RunDeadlineError` wraps `asyncio.timeout` around the provider call using `settings.run_deadline_s`.

## Code walkthrough

Provider prompts wrap outbound JSON in a digest-boundary block:

```python
def build_user_message(dto: BaseModel, *, judge: bool = False) -> str:
    payload = json.dumps(dto.model_dump(), ensure_ascii=True, sort_keys=True)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    boundary = f"DATA-{digest}"
    ...
```

`create_run()` then persists `RunData` with drafts, evidence, and the truth report.

Open `assemble_drafts()` to see how cover claims are capped by `max_cover_claims` from outbound settings and how missing questions still produce empty answer shells.

## Checkpoint

Run: `uv run pytest tests/unit/test_prompts.py tests/integration/test_pipeline.py`

## Exercise

Enable judge in settings and run an integration test with `MockProvider`. Compare `report.flagged_ids` before and after `prune_run()` to see which sentences survive.

Open `export.is_stale()` and note which two version strings must match for the UI to treat an old run as still valid.
