import pytest

from jaa.truth.dates import extract_spans
from jaa.truth.extractors import (
    extract_durations,
    extract_numbers,
    extract_orgs,
    extract_ownership,
    extract_skill_versions,
    extract_years,
    negated_terms,
)
from jaa.truth.lexicon import SkillLexicon

LEX = SkillLexicon.load(None)


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("team of 15 analysts", 15),
        ("15-person team", 15),
        ("1,200 widgets", 1200),
        ("40% growth", 40),
        ("2M users", 2),
        ("3rd attempt", 3),
        ("zero defects", 0),
        ("twelve engineers", 12),
    ],
)
def test_extract_numbers(text: str, value: int) -> None:
    nums = [n.value for n in extract_numbers(text) if isinstance(n.value, int)]
    assert value in nums


@pytest.mark.parametrize(
    ("text", "year"),
    [
        ("graduated in 2014", 2014),
        ("from 2019 to 2021", 2019),
        ("from 2019 to 2021", 2021),
    ],
)
def test_extract_years(text: str, year: int) -> None:
    assert year in extract_years(text)


@pytest.mark.parametrize(
    ("text", "present"),
    [
        ("Mar 2019 – present", True),
        ("03/2019–06/2021", False),
        ("2019–2021", False),
    ],
)
def test_extract_spans(text: str, present: bool) -> None:
    spans = extract_spans(text, __import__("datetime").date(2026, 10, 23))
    if present:
        assert any(getattr(s, "end_is_present", False) or "present" in s.raw.lower() for s in spans)
    else:
        assert spans


@pytest.mark.parametrize(
    ("text", "years"),
    [
        ("6 years of experience", 6),
        ("6+ years", 6),
        ("over 6 years", 6),
    ],
)
def test_extract_durations(text: str, years: int) -> None:
    durs = extract_durations(text)
    assert any(d.years == years for d in durs)


def test_org_initech() -> None:
    orgs = extract_orgs("At Initech, I built things.", LEX)
    assert "Initech" in orgs


def test_extract_ownership_active() -> None:
    assert "manage" in extract_ownership("I managed the team")


def test_extract_ownership_passive() -> None:
    assert extract_ownership("supported a migration led by another team") == set()


def test_negation_window() -> None:
    evidence = "No production experience with Kubernetes"
    claim = "I have production experience with Kubernetes"
    assert "kubernetes" in negated_terms(evidence, ["kubernetes"])
    assert "kubernetes" not in negated_terms(claim, ["kubernetes"])


@pytest.mark.parametrize(
    ("text", "pair"),
    [
        ("Python 3.12", ("python", "3.12")),
        ("Python 3.13", ("python", "3.13")),
    ],
)
def test_skill_versions(text: str, pair: tuple[str, str]) -> None:
    found = extract_skill_versions(text, LEX)
    assert pair in {(a.lower(), b) for a, b in found}
