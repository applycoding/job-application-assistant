import os
from pathlib import Path

import pytest

from jaa.generation.pipeline import Deps, create_run
from jaa.models import RunOptions
from jaa.samples import seed
from tests.support.golden import assert_golden_run


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("title_part", "golden_name"),
    [
        ("Acme", "job01_run.json"),
        ("Globex", "job02_run.json"),
        ("Vandelay", "job03_run.json"),
    ],
)
async def test_job_golden_run(
    app, settings, fixed_clock, seq_ids, title_part: str, golden_name: str
):
    repo = app.state.repo
    lex = app.state.lexicon
    seed(repo, settings, fixed_clock, seq_ids, lex)
    from tests.support.jobs import job_with_marker

    job = job_with_marker(repo.list_jobs(), title_part)
    deps = Deps(
        repo=repo,
        provider=app.state.provider,
        settings=settings,
        lexicon=lex,
        clock=fixed_clock,
        ids=seq_ids,
    )
    run = await create_run(deps, job.id, RunOptions(judge=False))
    update = os.environ.get("JAA_UPDATE_GOLDEN") == "1"
    assert_golden_run(run, str(Path("tests/golden") / golden_name), update=update)
