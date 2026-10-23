---
modules: src/jaa/config.py src/jaa/clock.py
checkpoint: uv run pytest tests/unit/test_config.py
---

# Setup and config

## Goal

Configure JAA through environment variables and an optional `.env` file, and see why injectable clocks matter for reproducible tests.

## Files

- `src/jaa/config.py` defines `Settings` and merges OS env with parsed `.env` lines.
- `src/jaa/clock.py` provides `SystemClock` and `FixedClock` behind a small `Clock` protocol.
- `src/jaa/resources/providers.toml` lists default models and API key env var names for real providers.

## Concepts

`Settings` is a Pydantic model. Important fields include `provider` (`mock` by default), `db_path`, `judge` (enable LLM judge), `reference_date` (freeze "today" for date checks), and upload or timeout limits.

`from_env()` reads `JAA_*` variables (see tests for the exact mapping). Paths like `db_path` accept strings and become `Path` objects via a validator.

`FixedClock` lets unit tests assert job parsing or retention logic against a known UTC instant without flaking on the calendar date.

## Code walkthrough

Environment keys are read with explicit precedence:

```python
def get(key: str) -> str | None:
    return _coalesce(raw_env, key, file_vars)
```

`resolved_reference_date()` picks `reference_date` or falls back to the clock's current date for tenure math.

`resolved_models()` combines `provider`, optional `model` / `judge_model` overrides, and entries from `providers.toml` so adapters always receive a concrete model id.

## Checkpoint

Run: `uv run pytest tests/unit/test_config.py`

## Exercise

Create a `.env` with `JAA_PROVIDER=mock` and `JAA_DB_PATH=var/tutorial.sqlite3`. Run `uv run jaa reset` (if available) or delete that file, then `uv run jaa seed` and confirm the database path matches your setting.

In a REPL, construct `Settings.from_env(env={"JAA_JUDGE": "true"})` and verify `judge` becomes true without touching unrelated fields.
