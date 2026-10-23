from datetime import date

from jaa.models import Sentence
from jaa.truth.deterministic import CheckContext, check_sentence
from jaa.truth.lexicon import SkillLexicon


def test_no_citation_fails():
    ctx = CheckContext(
        lexicon=SkillLexicon.load(None), reference_date=date(2026, 10, 23), target_company=None
    )
    s = Sentence(
        id="Q1.S1",
        kind="claim",
        text="I did things",
        citations=[],
        requirement_ids=[],
        rationale="",
    )
    assert check_sentence(s, {}, ctx).status == "unsupported"
