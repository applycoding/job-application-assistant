"""Limit enforcement (PLAN §5.3 / §6)."""

from __future__ import annotations

import asyncio
from io import BytesIO
from unittest.mock import patch

import pytest
from starlette.datastructures import UploadFile

from jaa.generation.pipeline import Deps, create_run
from jaa.ingest.loaders import read_upload_limited
from jaa.limits import MAX_JOB_CHARS
from jaa.models import RunOptions
from jaa.samples import seed


@pytest.mark.asyncio
async def test_upload_stops_at_max_plus_one_byte(settings, app, client):
    settings.max_upload_mb = 1
    app.state.settings = settings
    limit = settings.max_upload_mb * 1024 * 1024
    data = b"x" * (limit + 1)
    upload = UploadFile(filename="big.txt", file=BytesIO(data))
    with patch("jaa.limits.UPLOAD_READ_CHUNK", 64):
        from jaa.ingest.loaders import UploadTooLarge

        with pytest.raises(UploadTooLarge):
            await read_upload_limited(upload, limit)
    r = client.post(
        "/api/documents",
        files={"file": ("big.txt", data, "text/plain")},
    )
    assert r.status_code == 413


@pytest.mark.asyncio
async def test_corpus_chunk_limit_returns_422(settings, app, client, monkeypatch):
    settings.max_upload_mb = 20
    app.state.settings = settings
    monkeypatch.setattr("jaa.storage.repo.MAX_CORPUS_CHUNKS", 10)
    line = "- bullet line with enough tokens to pass filter\n"
    body = (line * 50).encode()
    r = client.post(
        "/api/documents",
        files={"file": ("huge.md", body, "text/plain")},
    )
    assert r.status_code == 422
    assert "Corpus exceeds" in r.json()["detail"] or "chunks" in r.json()["detail"].lower()


def test_job_text_too_long_returns_422(client):
    text = "x" * (MAX_JOB_CHARS + 1)
    r = client.post("/api/jobs", json={"text": text})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_run_deadline_504_no_run_row(settings, app, repo, fixed_clock, seq_ids):
    seed(repo, settings, fixed_clock, seq_ids, app.state.lexicon)
    job = repo.list_jobs()[0]
    settings.run_deadline_s = 1.0

    class SlowProvider:
        name = "slow"
        model = "slow"
        judge_model = "slow"

        async def draft(self, _req):  # type: ignore[no-untyped-def]
            await asyncio.sleep(2)
            raise RuntimeError("should not finish")

        async def judge(self, _req):  # type: ignore[no-untyped-def]
            raise RuntimeError("no judge")

    provider = SlowProvider()
    deps = Deps(
        repo=repo,
        provider=provider,
        settings=settings,
        lexicon=app.state.lexicon,
        clock=fixed_clock,
        ids=seq_ids,
    )
    from jaa.generation.pipeline import RunDeadlineError

    with pytest.raises(RunDeadlineError):
        await create_run(deps, job.id, RunOptions())
    assert repo.list_runs(job.id) == []
