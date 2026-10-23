---
modules: src/jaa/jobs/parser.py
checkpoint: uv run pytest tests/unit/test_job_parser.py tests/unit/test_requirements.py
---

# Parsing job posts

## Goal

Convert pasted or uploaded job text into a structured `JobPost`: title, company, prioritized requirements, and application questions.

## Files

- `src/jaa/jobs/parser.py` implements heading detection, company heuristics, and section routing.
- `src/jaa/jobs/requirements.py` extracts bullet requirements and stable requirement ids.
- `src/jaa/models.py` defines `JobPost`, `Requirement`, and `Question` shapes used everywhere downstream.

## Concepts

Job text is normalized with Unicode NFKC before parsing. Section headings match fuzzy keys such as "must have" or "nice to have" via `_match_section()`. Questions live under headings like "Application questions".

`extract_requirements()` in `requirements.py` turns lines into `Requirement` records with `priority`, `text`, `terms`, and `skills` drawn from the lexicon. Limits like `MAX_REQUIREMENTS` prevent runaway posts from exhausting retrieval.

The parser rejects obvious sample banners (`FICTIONAL SAMPLE`) when configured, keeping tutorial data out of production-shaped flows.

## Code walkthrough

Read `parse_job_post()` (or the main entry used by the API): it scans lines, toggles current section, and accumulates requirements and questions. Company detection combines patterns such as `Title - Company`, `at Company`, and labeled `Company:` lines.

Requirement ids are derived from stable hashes of normalized text so retrieval and truth checks can refer to `R1`, `R2`, consistently in tests and UI.

## Checkpoint

Run: `uv run pytest tests/unit/test_job_parser.py tests/unit/test_requirements.py`

## Exercise

Paste a job with two must-have bullets and one nice-to-have skill into the UI parser endpoint or a unit test fixture. Assert that priorities and extracted `terms` match what you expect from `SkillLexicon`.
