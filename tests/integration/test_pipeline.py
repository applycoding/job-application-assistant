import os
from pathlib import Path

import pytest

from jaa.generation.pipeline import Deps, create_run
from jaa.models import RunOptions
from jaa.samples import seed
from tests.support.golden import assert_golden_run


@pytest.mark.asyncio
async def test_job01_golden(app, settings, fixed_clock, seq_ids):
    repo = app.state.repo
    lex = app.state.lexicon
    seed(repo, settings, fixed_clock, seq_ids, lex)
    jobs = repo.list_jobs()
    job01 = next(j for j in jobs if "Acme" in j.title)
    deps = Deps(
        repo=repo,
        provider=app.state.provider,
        settings=settings,
        lexicon=lex,
        clock=fixed_clock,
        ids=seq_ids,
    )
    run = await create_run(deps, job01.id, RunOptions(judge=False))
    golden = Path("tests/golden/job01_run.json")
    assert_golden_run(run, str(golden), update=os.environ.get("JAA_UPDATE_GOLDEN") == "1")
