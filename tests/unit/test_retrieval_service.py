from pathlib import Path

from jaa.clock import FixedClock
from jaa.ingest.chunker import chunk_document
from jaa.ingest.loaders import detect_media_type, load_lines
from jaa.jobs.parser import parse_job
from jaa.retrieval.service import retrieve_for_job
from jaa.truth.lexicon import SkillLexicon
from tests.conftest import FIXED_NOW


def test_gap_go():
    data = Path("samples/jobs/03-backend-python-developer-vandelay-health.md").read_text()
    job = parse_job(data, SkillLexicon.load(None), FixedClock(FIXED_NOW))
    cv = Path("samples/alex-doe-cv.md").read_bytes()
    mt = detect_media_type("cv.md", cv[:64])
    lines, _ = load_lines(cv, mt)
    chunks = chunk_document("d1", lines)
    res = retrieve_for_job(
        job, [c for c in chunks if c.kind not in ("heading", "contact")], SkillLexicon.load(None)
    )
    assert any(g.term == "FastAPI" for g in res.gaps if g.term)
