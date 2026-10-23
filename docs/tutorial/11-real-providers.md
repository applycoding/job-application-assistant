---
modules: src/jaa/providers/anthropic_provider.py
checkpoint: uv run pytest tests/adapters
---

# Real providers

## Goal

Wire Anthropic, OpenAI, Google, or xAI models through a shared structured-output adapter pattern while keeping secrets in environment variables.

## Files

- `src/jaa/providers/anthropic_provider.py` (and siblings `openai_provider.py`, `google_provider.py`) subclass `StructuredLLMProvider`.
- `src/jaa/providers/registry.py` loads `providers.toml` and constructs the correct class from `Settings.provider`.
- `src/jaa/providers/schema.py` defines JSON schemas sent to APIs for drafts and judge verdicts.

## Concepts

Real providers require `uv sync --extra llm` so optional HTTP clients import cleanly. `build_provider()` reads `key_env` from TOML and fails fast with `ProviderConfigError` when the API key is missing.

Each vendor exposes structured JSON differently; `providers.toml` `structured_output` flags must match what the adapter expects (`anthropic_output_config`, `openai_text_format`, etc.).

Adapters honor `settings.request_timeout_s`, share `CallBudget` limits in tests, and implement `aclose()` for connection hygiene (see app lifespan).

## Code walkthrough

Pick `AnthropicProvider._complete_json()`: it calls `messages.create` with a JSON schema payload, parses the tool or text response, and returns a string for `validate_draft()` or judge parsing.

Mirror the pattern in `OpenAIProvider` and `GoogleProvider` to see how only transport and request shape differ while `prompts.py` stays shared.

## Checkpoint

Run: `uv run pytest tests/adapters`

Adapter tests use recorded transports and never hit live APIs in CI.

## Exercise

Export a sandbox API key, set `JAA_PROVIDER=anthropic`, and run one local draft against a seeded job. Compare outbound redaction in logs or debug prints with the mock run for the same job id.
