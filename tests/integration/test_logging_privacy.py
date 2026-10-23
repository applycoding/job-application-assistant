"""Logs must not contain API keys or raw evidence payloads."""

from __future__ import annotations

import logging

import pytest

from jaa.generation.pipeline import Deps, create_run
from jaa.models import RunOptions
from jaa.samples import seed


@pytest.mark.asyncio
async def test_logs_exclude_keys_and_evidence(caplog, app, settings, repo, fixed_clock, seq_ids):
    caplog.set_level(logging.DEBUG)
    seed(repo, settings, fixed_clock, seq_ids, app.state.lexicon)
    from tests.support.jobs import job_with_marker

    job = job_with_marker(repo.list_jobs(), "Acme")
    chunk = repo.get_chunks(retrievable_only=True)[0]
    deps = Deps(
        repo=repo,
        provider=app.state.provider,
        settings=settings,
        lexicon=app.state.lexicon,
        clock=fixed_clock,
        ids=seq_ids,
    )
    await create_run(deps, job.id, RunOptions(judge=False))
    blob = caplog.text.lower()
    assert "api_key" not in blob
    assert "sk-" not in blob
    assert chunk.evidence_text[:40].lower() not in blob
