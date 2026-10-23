---
modules: scripts/check_repo.py
checkpoint: uv run pytest -m scenario
---

# Testing, CI, Docker, and privacy

## Goal

Understand how the repo stays safe to publish: policy scripts, scenario tests, redaction before LLM calls, and Docker ignore rules for secrets and databases.

## Files

- `scripts/check_repo.py` enforces fictional sample markers, blocks tracked secrets, and audits GitHub Actions pins.
- `src/jaa/privacy/redact.py` strips emails and phone patterns from outbound evidence.
- `src/jaa/privacy/outbound.py` applies redaction when building provider payloads.
- `tests/` holds unit, integration, adapter, and `-m scenario` end-to-end flows.

## Concepts

Sample CVs must contain the Alex Doe fictional banner so real PII never ships by accident. `check_repo.py` scans tracked files for `.env`, `var/`, raw sqlite paths, and disallowed phone numbers outside the `555-01` test prefix.

Scenario tests exercise ingest, job parse, run creation, and export paths together; mark them with `@pytest.mark.scenario` for selective CI jobs.

Docker builds should exclude credentials via `.dockerignore` entries validated by the same script (`DOCKERIGNORE_REQUIRED` tuple).

## Code walkthrough

Skim `check_repo.py` main: it runs git-aware checks locally and in CI before pytest. Open `redact()` to see regex replacements applied to chunk text and section titles in `OutboundEvidence`.

Read one scenario test module to see how `MockProvider` and `FixedClock` produce deterministic golden outputs.

## Checkpoint

Run: `uv run pytest -m scenario`

Also run `python scripts/check_repo.py` before opening a PR to catch policy violations early.

## Exercise

Introduce a deliberate policy violation in a throwaway branch (for example remove a fictional marker), run `check_repo.py`, then revert. Document the error message you saw for future contributors.
