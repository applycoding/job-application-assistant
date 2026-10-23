from pathlib import Path

import pytest

from jaa.generation.pipeline import Deps, create_run
from jaa.models import RunOptions
from jaa.samples import seed


@pytest.mark.asyncio
async def test_adversarial_delimiter_not_in_run_output(app, settings, repo, fixed_clock, seq_ids):
    seed(repo, settings, fixed_clock, seq_ids, app.state.lexicon)
    payload = Path("tests/fixtures/adversarial/delimiter_escape.txt").read_text(encoding="utf-8")
    data = payload.encode()
    import hashlib

    from jaa.ingest.loaders import detect_media_type, load_lines

    lines, warnings = load_lines(data, detect_media_type("adv.txt", data[:64]))
    sha = hashlib.sha256(data).hexdigest()
    repo.upsert_document("adv.txt", "txt", sha, lines, warnings)
    job = repo.list_jobs()[0]
    deps = Deps(
        repo=repo,
        provider=app.state.provider,
        settings=settings,
        lexicon=app.state.lexicon,
        clock=fixed_clock,
        ids=seq_ids,
    )
    run = await create_run(deps, job.id, RunOptions())
    dumped = run.model_dump_json()
    assert "IGNORE PREVIOUS" not in dumped
    assert "system:" not in dumped.lower()
