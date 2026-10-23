"""Build LLM provider from settings and providers.toml."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from jaa.config import Settings
from jaa.providers.base import CallBudget, LLMProvider, ProviderConfigError
from jaa.providers.mock import MockProvider

_PROVIDERS_TOML = Path(__file__).resolve().parent.parent / "resources" / "providers.toml"

_EXPECTED_FLAGS = {
    "anthropic": "anthropic_output_config",
    "openai": "openai_text_format",
    "google": "gemini_response_json_schema",
    "xai": "openai_text_format",
}


def load_provider_config(name: str) -> dict[str, Any]:
    data = tomllib.loads(_PROVIDERS_TOML.read_text(encoding="utf-8"))
    if name not in data:
        raise ProviderConfigError(f"Unknown provider in config: {name}")
    return dict(data[name])


def build_provider(settings: Settings, *, transport: Any | None = None) -> LLMProvider:
    name = settings.provider
    if name == "mock":
        return MockProvider()

    cfg = load_provider_config(name)
    expected = _EXPECTED_FLAGS.get(name)
    flag = cfg.get("structured_output")
    if expected and flag != expected:
        raise ProviderConfigError(
            f"structured_output mismatch for {name}: expected {expected}, got {flag}"
        )

    key_env = cfg.get("key_env")
    if not key_env:
        raise ProviderConfigError(f"key_env missing for provider {name}")
    api_key = os.environ.get(key_env, "")
    if not api_key:
        raise ProviderConfigError(f"Missing API key environment variable: {key_env}")

    model, judge_model = settings.resolved_models()
    budget = CallBudget()

    if name == "anthropic":
        from jaa.providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider(
            settings, api_key, model, judge_model, transport=transport, budget=budget
        )
    if name == "openai":
        from jaa.providers.openai_provider import OpenAIProvider

        return OpenAIProvider(
            settings,
            api_key,
            model,
            judge_model,
            store=bool(cfg.get("store", False)),
            transport=transport,
            budget=budget,
        )
    if name == "google":
        from jaa.providers.google_provider import GoogleProvider

        return GoogleProvider(settings, api_key, model, judge_model, budget=budget)
    if name == "xai":
        from jaa.providers.openai_provider import XAIProvider

        return XAIProvider(
            settings,
            api_key,
            model,
            judge_model,
            base_url=str(cfg.get("base_url", "https://api.x.ai/v1")),
            transport=transport,
            budget=budget,
        )

    raise ProviderConfigError(f"Unsupported provider: {name}")
