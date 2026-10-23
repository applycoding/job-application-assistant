---
modules: src/jaa/app.py
checkpoint: uv run jaa --help
---

# What we build

## Goal

Understand the end-to-end flow of the Job Application Assistant (JAA): ingest a CV corpus, parse a job post, retrieve evidence, draft answers with citations, and verify claims before you copy text into an application.

## Files

- `src/jaa/app.py` wires FastAPI, SQLite, the skill lexicon, and an LLM provider.
- `src/jaa/cli.py` exposes `serve`, `seed`, `ingest`, and `reset` for local workflows.
- `src/jaa/generation/pipeline.py` orchestrates retrieval, drafting, truth checks, and persistence.

## Concepts

A **run** is one attempt to answer a stored job using the current corpus snapshot. Runs are versioned: `corpus_version` and `CHECK_RULES_VERSION` let you tell whether old drafts are stale after you upload new documents or change check rules.

The stack favors **local-first** storage (`var/jaa.sqlite3` by default) and a **mock provider** so CI and tutorials work without API keys. Real providers plug in through `src/jaa/providers/registry.py`.

## Code walkthrough

`create_app()` in `app.py` loads `Settings.from_env()`, opens the database via `create_db_engine`, loads `SkillLexicon`, builds `Repository`, and calls `build_provider(cfg)`. Application state holds `repo`, `provider`, `csrf_token`, and related services for HTML and JSON routes.

The lifespan handler closes async HTTP clients when the server shuts down, which matters for Anthropic, OpenAI, and Google adapters.

## Checkpoint

Run: `uv run jaa --help`

You should see subcommands for serving the UI and managing documents. If imports fail, run `uv sync` from the repo root first.

## Exercise

Start the app with `uv run jaa serve`, open the UI, and upload one sample from `samples/`. Note which tables change by inspecting `var/jaa.sqlite3` with any SQLite browser after a successful ingest.
