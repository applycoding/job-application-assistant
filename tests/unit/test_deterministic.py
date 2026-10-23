"""Deterministic checks: one pass/fail pair per CheckName plus honesty cases."""

from datetime import date

from jaa.models import Chunk, Sentence
from jaa.truth.deterministic import CheckContext, check_sentence
from jaa.truth.lexicon import SkillLexicon

REF = date(2026, 10, 23)
LEX = SkillLexicon.load(None)
CTX = CheckContext(lexicon=LEX, reference_date=REF, target_company=None)


def _chunk(cid: str, text: str) -> Chunk:
    return Chunk(
        id=cid,
        doc_id="d",
        line_no=1,
        kind="bullet",
        text=text,
        section="Experience",
    )


def _claim(text: str, citations: list[str], cid: str = "c1") -> Sentence:
    return Sentence(
        id="Q1.S1",
        kind="claim",
        text=text,
        citations=citations or [cid],
        requirement_ids=[],
        rationale="",
    )


def test_no_citation_fails() -> None:
    s = Sentence(
        id="Q1.S1",
        kind="claim",
        text="I did things",
        citations=[],
        requirement_ids=[],
        rationale="",
    )
    assert check_sentence(s, {}, CTX).status == "unsupported"


def test_invalid_citation_fails() -> None:
    s = _claim("I led a team.", ["missing"])
    r = check_sentence(s, {}, CTX)
    assert r.status == "unsupported"
    assert any(f.check == "invalid_citation" for f in r.failures)


def test_number_mismatch_fails() -> None:
    c = _chunk("c1", "Team of 10 analysts.")
    s = _claim("I led a team of 15 analysts.", ["c1"])
    r = check_sentence(s, {"c1": c}, CTX)
    assert r.status == "unsupported"
    assert any(f.check == "number" for f in r.failures)


def test_number_match_passes() -> None:
    c = _chunk("c1", "Team of 15 analysts.")
    s = _claim("Our team had 15 analysts.", ["c1"])
    assert check_sentence(s, {"c1": c}, CTX).status == "checks_passed"


def test_year_mismatch_fails() -> None:
    c = _chunk("c1", "Graduated in 2014.")
    s = _claim("I graduated in 2020.", ["c1"])
    r = check_sentence(s, {"c1": c}, CTX)
    assert any(f.check == "year" for f in r.failures)


def test_employer_mismatch_fails() -> None:
    c = _chunk("c1", "Worked at Contoso Retail.")
    s = _claim("I worked at Initech.", ["c1"])
    r = check_sentence(s, {"c1": c}, CTX)
    assert any(f.check == "employer" for f in r.failures)


def test_ownership_mismatch_fails() -> None:
    c = _chunk("c1", "Supported a migration led by another team.")
    s = _claim("I led the migration.", ["c1"])
    r = check_sentence(s, {"c1": c}, CTX)
    assert any(f.check == "ownership" for f in r.failures)


def test_negation_mismatch_fails() -> None:
    c = _chunk("c1", "No production Kubernetes experience.")
    s = _claim("I have production Kubernetes experience.", ["c1"])
    r = check_sentence(s, {"c1": c}, CTX)
    assert any(f.check == "negation" for f in r.failures)


def test_mixed_citations_fails() -> None:
    c1 = _chunk("c1", "Worked with 15 analysts.")
    c2 = _chunk("c2", "Led a team of 2.")
    s = _claim("I led a team of 15 analysts.", ["c1", "c2"])
    r = check_sentence(s, {"c1": c1, "c2": c2}, CTX)
    assert any(f.check == "mixed_citations" for f in r.failures)


def test_skill_missing_fails() -> None:
    c = _chunk("c1", "Built SQL reports.")
    s = _claim("I used Python daily.", ["c1"])
    r = check_sentence(s, {"c1": c}, CTX)
    assert any(f.check == "skill" for f in r.failures)


def test_skill_version_mismatch_fails() -> None:
    c = _chunk("c1", "Python 3.12 in production.")
    s = _claim("Python 3.13 in production.", ["c1"])
    r = check_sentence(s, {"c1": c}, CTX)
    assert any(f.check == "skill_version" for f in r.failures)


def test_duration_year_only_not_verified() -> None:
    c = _chunk("c1", "Python (2020-2026)")
    s = _claim("6 years of Python experience", ["c1"])
    r = check_sentence(s, {"c1": c}, CTX)
    assert r.status == "not_verified"
    assert any(f.check == "duration" for f in r.failures)


def test_year_match_passes() -> None:
    c = _chunk("c1", "Graduated in 2014.")
    s = _claim("I graduated in 2014.", ["c1"])
    assert check_sentence(s, {"c1": c}, CTX).status == "checks_passed"


def test_employer_match_passes() -> None:
    c = _chunk("c1", "Worked at Contoso Retail.")
    s = _claim("I worked at Contoso Retail.", ["c1"])
    assert check_sentence(s, {"c1": c}, CTX).status == "checks_passed"


def test_ownership_match_passes() -> None:
    c = _chunk("c1", "I led the migration.")
    s = _claim("I led the migration.", ["c1"])
    assert check_sentence(s, {"c1": c}, CTX).status == "checks_passed"


def test_negation_aligned_passes() -> None:
    c = _chunk("c1", "No production Kubernetes experience.")
    s = _claim("I have no production Kubernetes experience.", ["c1"])
    assert check_sentence(s, {"c1": c}, CTX).status == "checks_passed"


def test_mixed_citations_single_chunk_passes() -> None:
    c = _chunk("c1", "Led a team of 15 analysts.")
    s = _claim("I led a team of 15 analysts.", ["c1"])
    assert check_sentence(s, {"c1": c}, CTX).status == "checks_passed"


def test_skill_match_passes() -> None:
    c = _chunk("c1", "Built SQL and Python reports.")
    s = _claim("I used Python daily.", ["c1"])
    assert check_sentence(s, {"c1": c}, CTX).status == "checks_passed"


def test_skill_version_match_passes() -> None:
    c = _chunk("c1", "Python 3.12 in production.")
    s = _claim("Shipped on Python 3.12.", ["c1"])
    assert check_sentence(s, {"c1": c}, CTX).status == "checks_passed"


def test_duration_explicit_years_passes() -> None:
    c = _chunk("c1", "Over 6 years of Python delivery.")
    s = _claim("6 years of Python experience.", ["c1"])
    assert check_sentence(s, {"c1": c}, CTX).status == "checks_passed"


def test_valid_citation_passes() -> None:
    c = _chunk("c1", "General experience.")
    s = _claim("General experience noted.", ["c1"])
    assert check_sentence(s, {"c1": c}, CTX).status == "checks_passed"


def test_framing_skips_checks() -> None:
    s = Sentence(
        id="C.F1",
        kind="framing",
        text="Dear team,",
        citations=[],
        requirement_ids=[],
        rationale="",
    )
    assert check_sentence(s, {}, CTX).status == "checks_passed"
