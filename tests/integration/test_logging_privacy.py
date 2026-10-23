"""Logs must not contain API keys or raw evidence payloads."""

from __future__ import annotations

import logging

import pytest

from jaa.app import create_app
from jaa.config import Settings
from jaa.generation.pipeline import Deps, create_run
from jaa.models import RunOptions
from jaa.providers.registry import build_provider
from jaa.samples import seed

SENTINEL = "sk-sentinel-must-not-appear-in-logs-7f3a"
KEY_ENVS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "XAI_API_KEY")


@pytest.mark.asyncio
async def test_logs_exclude_provider_keys_and_evidence(
    caplog, settings, repo, fixed_clock, seq_ids, monkeypatch: pytest.MonkeyPatch, tmp_path
):
    for name in KEY_ENVS:
        monkeypatch.setenv(name, SENTINEL)
    caplog.set_level(logging.DEBUG)
    application = create_app(settings)
    from tests.conftest import _wire_test_app

    _wire_test_app(application, settings, fixed_clock, seq_ids)
    seed(repo, settings, fixed_clock, seq_ids, application.state.lexicon)
    from tests.support.jobs import job_with_marker

    job = job_with_marker(repo.list_jobs(), "Acme")
    chunks = repo.get_chunks(retrievable_only=True)
    evidence_snippets = [c.evidence_text for c in chunks[:5]]
    deps = Deps(
        repo=repo,
        provider=application.state.provider,
        settings=settings,
        lexicon=application.state.lexicon,
        clock=fixed_clock,
        ids=seq_ids,
    )
    await create_run(deps, job.id, RunOptions(judge=False))
    for record in caplog.records:
        msg = record.getMessage()
        assert SENTINEL not in msg
        assert "api_key" not in msg.lower()
        for snippet in evidence_snippets:
            if snippet.strip():
                assert snippet not in msg


def test_registry_build_provider_does_not_log_keys(caplog, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in KEY_ENVS:
        monkeypatch.setenv(name, SENTINEL)
    caplog.set_level(logging.DEBUG)
    settings = Settings(provider="openai", model="gpt-4o-mini")
    provider = build_provider(settings, transport=object())
    assert provider.model
    for record in caplog.records:
        assert SENTINEL not in record.getMessage()
