from pathlib import Path

from jaa.clock import FixedClock
from jaa.jobs.parser import parse_job
from jaa.truth.lexicon import SkillLexicon
from tests.conftest import FIXED_NOW


def test_sample_job01():
    text = Path("samples/jobs/01-senior-data-engineer-acme-logistics.md").read_text()
    job = parse_job(text, SkillLexicon.load(None), FixedClock(FIXED_NOW))
    assert job.title == "Senior Data Engineer"
    assert job.company == "Acme Logistics"
    assert job.requirements
    assert "Alex Doe" not in (job.company or "")
