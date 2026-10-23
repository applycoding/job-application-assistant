"""Concurrency: snapshot before provider call, atomic replace (PLAN §7.3 / §22)."""

from __future__ import annotations

import asyncio
import hashlib
import threading
from pathlib import Path

import pytest
from sqlalchemy import text

from jaa.export import is_stale
from jaa.generation.pipeline import Deps, create_run
from jaa.ingest.loaders import detect_media_type, load_lines
from jaa.models import RunOptions
from jaa.providers.mock import MockProvider
from jaa.samples import seed


class BlockingMock(MockProvider):
    def __init__(self) -> None:
        super().__init__()
        self._gate = threading.Event()

    def release(self) -> None:
        self._gate.set()

    async def draft(self, req):  # type: ignore[no-untyped-def]
        if not self._gate.wait(timeout=15):
            raise TimeoutError("blocking mock timed out")
        return await super().draft(req)


@pytest.mark.asyncio
async def test_generate_holds_pre_call_corpus_version(app, settings, repo, fixed_clock, seq_ids):
    seed(repo, settings, fixed_clock, seq_ids, app.state.lexicon)
    from tests.support.jobs import job_with_marker

    job = job_with_marker(repo.list_jobs(), "Acme")
    ref = settings.reference_date
    assert ref is not None
    version_before, _ = repo.corpus_snapshot(ref)

    blocker = BlockingMock()
    deps = Deps(
        repo=repo,
        provider=blocker,
        settings=settings,
        lexicon=app.state.lexicon,
        clock=fixed_clock,
        ids=seq_ids,
    )

    cv_path = Path("samples/alex-doe-cv.md")
    edited = cv_path.read_text(encoding="utf-8").replace("40%", "39%")

    async def run_generate() -> None:
        await create_run(deps, job.id, RunOptions(judge=False))

    task = asyncio.create_task(run_generate())

    def replace_cv() -> None:
        data = edited.encode()
        sha = hashlib.sha256(data).hexdigest()
        lines, warnings = load_lines(data, detect_media_type("alex-doe-cv.md", data[:64]))
        repo.upsert_document("alex-doe-cv.md", "md", sha, lines, warnings)
        blocker.release()

    threading.Thread(target=replace_cv, daemon=True).start()

    await task
    runs = repo.list_runs(job.id)
    assert len(runs) == 1
    run = runs[0]
    assert run.corpus_version == version_before
    version_after, chunks_after = repo.corpus_snapshot(ref)
    assert version_after != version_before
    assert is_stale(run, version_after)
    assert len(chunks_after) > 0


@pytest.mark.asyncio
async def test_second_connection_begin_immediate_during_provider(
    app, settings, repo, fixed_clock, seq_ids
):
    seed(repo, settings, fixed_clock, seq_ids, app.state.lexicon)
    job = repo.list_jobs()[0]
    engine = app.state.engine
    blocker = BlockingMock()
    deps = Deps(
        repo=repo,
        provider=blocker,
        settings=settings,
        lexicon=app.state.lexicon,
        clock=fixed_clock,
        ids=seq_ids,
    )

    acquired = threading.Event()

    def try_immediate() -> None:
        with engine.connect() as conn:
            conn.execute(text("BEGIN IMMEDIATE"))
            acquired.set()
            conn.commit()

    async def run_generate() -> None:
        await create_run(deps, job.id, RunOptions())

    task = asyncio.create_task(run_generate())
    threading.Thread(target=try_immediate, daemon=True).start()
    assert acquired.wait(timeout=0.1)
    blocker.release()
    await task
