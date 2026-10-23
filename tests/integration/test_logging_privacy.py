"""Logs must not contain API keys or raw evidence payloads."""

from __future__ import annotations

import logging

import pytest

from jaa.generation.pipeline import Deps, create_run
from jaa.models import RunOptions
from jaa.samples import seed

SENTINEL_KEY = "JAA_LOG_LEAK_SENTINEL"
SENTINEL_VALUE = "sk-sentinel-must-not-appear-in-logs-7f3a"


@pytest.mark.asyncio
async def test_logs_exclude_sentinel_and_evidence(
    caplog, app, settings, repo, fixed_clock, seq_ids, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv(SENTINEL_KEY, SENTINEL_VALUE)
    settings.log_leak_sentinel = SENTINEL_VALUE
    caplog.set_level(logging.DEBUG, logger="jaa.generation.pipeline")
    seed(repo, settings, fixed_clock, seq_ids, app.state.lexicon)
    from tests.support.jobs import job_with_marker

    job = job_with_marker(repo.list_jobs(), "Acme")
    chunks = repo.get_chunks(retrievable_only=True)
    evidence_snippets = [c.evidence_text for c in chunks[:5]]
    deps = Deps(
        repo=repo,
        provider=app.state.provider,
        settings=settings,
        lexicon=app.state.lexicon,
        clock=fixed_clock,
        ids=seq_ids,
    )
    await create_run(deps, job.id, RunOptions(judge=False))
    for record in caplog.records:
        msg = record.getMessage()
        assert SENTINEL_VALUE not in msg
        assert "api_key" not in msg.lower()
        for snippet in evidence_snippets:
            if snippet.strip():
                assert snippet not in msg
