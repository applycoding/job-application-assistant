import pytest

from jaa.truth.extractors import extract_numbers, extract_orgs
from jaa.truth.lexicon import SkillLexicon


@pytest.mark.parametrize("text,exp", [("team of 15 analysts", 15), ("15-person team", 15)])
def test_numbers(text, exp):
    nums = [n.value for n in extract_numbers(text)]
    assert exp in nums


def test_org_initech():
    orgs = extract_orgs("At Initech, I built things.", SkillLexicon.load(None))
    assert "Initech" in orgs
