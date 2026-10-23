---
modules: src/jaa/truth/deterministic.py
checkpoint: uv run pytest tests/unit/test_extractors.py tests/unit/test_dates.py tests/unit/test_deterministic.py
---

# Truthfulness (deterministic checks)

## Goal

Learn how JAA verifies each draft sentence against cited CV chunks without calling an LLM, using explicit extractors and versioned rule sets.

## Files

- `src/jaa/truth/deterministic.py` runs per-sentence checks and sets `CHECK_RULES_VERSION`.
- `src/jaa/truth/extractors.py` finds numbers, org names, skills, durations, and negated terms in text.
- `src/jaa/truth/dates.py` parses employment date spans and compares them to a reference date.
- `src/jaa/truth/verdict.py` maps failures to statuses like `unsupported` or `checks_passed`.

## Concepts

Every claim sentence must cite at least one chunk id present in the retrieval pool. Checks include citation presence, numeric consistency, organization mentions, skill versions, ownership language, and tenure relative to `CheckContext.reference_date`.

Framing sentences (`kind="framing"`) short-circuit to `checks_passed` because they introduce answers rather than assert CV facts.

`CHECK_RULES_VERSION` bumps when rules change; combined with `corpus_version` it powers stale-run detection in `export.is_stale()`.

## Code walkthrough

Skill tokens allow a sentence-ending period without swallowing `Node.js`:

```python
_SKILL_TERM_TRAIL = r"(?![A-Za-z0-9+#])"
```

Duration extraction treats `over` / `more than` as strict lower bounds:

```python
_DURATION_RE = re.compile(
    r"\b(over|more than)\s+(\d+)\+?\s*years?\b|\b(\d+)\+?\s*years?\b",
    re.IGNORECASE,
)
```

Read `check_sentence()` and `_check_duration()` together to see how explicit year counts and employment spans interact.

## Checkpoint

Run: `uv run pytest tests/unit/test_extractors.py tests/unit/test_dates.py tests/unit/test_deterministic.py`

## Exercise

Craft a one-sentence claim that cites a chunk but states a team size not present in the chunk text. Unit-test `check_sentence()` and confirm the appropriate `CheckFailure` check name appears.

Find where `target_company` from the job post influences org-related failures in `deterministic.py`.
