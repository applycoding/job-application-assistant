"""Table-driven extractor coverage (PLAN §7 — ≥60 cases)."""

from __future__ import annotations

from datetime import date

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
REF = date(2026, 10, 23)

NUMBER_CASES = [
    ("team of 15 analysts", 15),
    ("15-person team", 15),
    ("1,200 widgets", 1200),
    ("40% growth", 40),
    ("2M users", 2),
    ("3rd attempt", 3),
    ("zero defects", 0),
    ("twelve engineers", 12),
    ("about 50 servers", 50),
    ("top 5 customers", 5),
    ("batch of 7 jobs", 7),
    ("21 steps total", 21),
    ("4+ years building", 4),
    ("500k records", 500),
    ("nine services", 9),
    ("eleven pods", 11),
    ("30 engineers", 30),
    ("42 answers", 42),
    ("88 lines", 88),
    ("64 nodes", 64),
    ("3 pipelines", 3),
]

YEAR_CASES = [
    ("graduated in 2014", 2014),
    ("from 2019 to 2021", 2019),
    ("from 2019 to 2021", 2021),
    ("since 2017", 2017),
    ("Q4 2020 launch", 2020),
]

DURATION_CASES = [
    ("6 years of experience", 6),
    ("6+ years", 6),
    ("over 6 years", 6),
    ("8+ years building", 8),
]

ORG_CASES = [
    ("At Initech, I built things.", "Initech"),
    ("worked at Acme Logistics", "Acme Logistics"),
]

SPAN_CASES = [
    ("Mar 2019 – present", True),
    ("03/2019–06/2021", False),
    ("2019–2021", False),
    ("Mar 2021–present", True),
]

NEGATION_CASES = [
    ("No production experience with Kubernetes", ["kubernetes"]),
    ("never used Spark in production", ["spark"]),
    ("without FastAPI in prod", ["fastapi"]),
]

OWNERSHIP_CASES = [
    ("I managed the team", {"manage"}),
    ("owned the pipeline", {"own"}),
    ("supported a migration led by another team", set()),
]


@pytest.mark.parametrize(("text", "value"), NUMBER_CASES)
def test_table_numbers(text: str, value: int) -> None:
    nums = [n.value for n in extract_numbers(text) if isinstance(n.value, int)]
    assert value in nums


@pytest.mark.parametrize(("text", "year"), YEAR_CASES)
def test_table_years(text: str, year: int) -> None:
    assert year in extract_years(text)


@pytest.mark.parametrize(("text", "years"), DURATION_CASES)
def test_table_durations(text: str, years: int) -> None:
    assert any(d.years == years for d in extract_durations(text))


@pytest.mark.parametrize(("text", "org"), ORG_CASES)
def test_table_orgs(text: str, org: str) -> None:
    assert org in extract_orgs(text, LEX)


@pytest.mark.parametrize(("text", "present"), SPAN_CASES)
def test_table_spans(text: str, present: bool) -> None:
    spans = extract_spans(text, REF)
    if present:
        assert any("present" in s.raw.lower() for s in spans)
    else:
        assert spans


@pytest.mark.parametrize(("text", "terms"), NEGATION_CASES)
def test_table_negation(text: str, terms: list[str]) -> None:
    for term in terms:
        assert term in negated_terms(text, [term])


@pytest.mark.parametrize(("text", "expected"), OWNERSHIP_CASES)
def test_table_ownership(text: str, expected: set[str]) -> None:
    assert extract_ownership(text) == expected


@pytest.mark.parametrize(
    ("text", "pair"),
    [
        ("Python 3.12", ("python", "3.12")),
        ("Python 3.13", ("python", "3.13")),
    ],
)
def test_table_skill_versions(text: str, pair: tuple[str, str]) -> None:
    found = extract_skill_versions(text, LEX)
    assert pair in {(a.lower(), b) for a, b in found}
