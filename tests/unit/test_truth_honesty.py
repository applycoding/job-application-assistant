"""Honesty regressions from independent verification."""

from datetime import date

from jaa.models import Chunk, Sentence
from jaa.truth.deterministic import CheckContext, check_sentence
from jaa.truth.extractors import extract_orgs, extract_ownership, negated_terms
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


def test_negation_with_trailing_period_on_term() -> None:
    evidence = "No production experience with Kubernetes."
    claim = "I have production experience with Kubernetes."
    assert "kubernetes" in negated_terms(evidence, ["kubernetes"])
    assert "kubernetes" not in negated_terms(claim, ["kubernetes"])
    c = _chunk("c1", evidence)
    s = Sentence(
        id="Q1.S1",
        kind="claim",
        text=claim,
        citations=["c1"],
        requirement_ids=[],
        rationale="",
    )
    assert check_sentence(s, {"c1": c}, CTX).status == "unsupported"


def test_negation_never_used_vs_positive_evidence() -> None:
    claim = "I have never used Kubernetes."
    evidence = "Ran Kubernetes in production."
    assert "kubernetes" in negated_terms(claim, ["kubernetes"])
    c = _chunk("c1", evidence)
    s = Sentence(
        id="Q1.S1",
        kind="claim",
        text=claim,
        citations=["c1"],
        requirement_ids=[],
        rationale="",
    )
    assert check_sentence(s, {"c1": c}, CTX).status == "unsupported"


def test_skill_missing_at_sentence_end_unsupported() -> None:
    c = _chunk("c1", "Built services in Python.")
    for claim in (
        "I have deep expertise in Kubernetes.",
        "I am certified in AWS.",
        "Most of my work used Terraform.",
    ):
        s = Sentence(
            id="Q1.S1",
            kind="claim",
            text=claim,
            citations=["c1"],
            requirement_ids=[],
            rationale="",
        )
        result = check_sentence(s, {"c1": c}, CTX)
        assert result.status == "unsupported"
        assert any(f.check == "skill" for f in result.failures)


def test_skill_present_at_sentence_end_passes() -> None:
    c = _chunk("c1", "Built services in Python.")
    s = Sentence(
        id="Q1.S1",
        kind="claim",
        text="I have shipped features in Python.",
        citations=["c1"],
        requirement_ids=[],
        rationale="",
    )
    assert check_sentence(s, {"c1": c}, CTX).status == "checks_passed"


def test_negation_kafka_sentence_end() -> None:
    c = _chunk("c1", "Built Kafka pipelines.")
    s = Sentence(
        id="Q1.S1",
        kind="claim",
        text="I never used Kafka.",
        citations=["c1"],
        requirement_ids=[],
        rationale="",
    )
    assert check_sentence(s, {"c1": c}, CTX).status == "unsupported"


def test_ownership_led_active_not_wiped_by_passive_clause() -> None:
    assert "lead" in extract_ownership("I led the migration.")
    assert extract_ownership("Supported a migration led by another team.") == set()


def test_mixed_citations_team_size() -> None:
    c1 = _chunk("c1", "Worked with 15 analysts.")
    c2 = _chunk("c2", "Led a team of 2.")
    s = Sentence(
        id="Q1.S1",
        kind="claim",
        text="I led a team of 15 analysts.",
        citations=["c1", "c2"],
        requirement_ids=[],
        rationale="",
    )
    result = check_sentence(s, {"c1": c1, "c2": c2}, CTX)
    assert result.status == "unsupported"
    assert any(f.check == "mixed_citations" for f in result.failures)


def test_duration_year_only_span_not_verified() -> None:
    chunk = _chunk("c1", "Python work (2020-2026)")
    s = Sentence(
        id="Q1.S1",
        kind="claim",
        text="6 years of Python experience",
        citations=["c1"],
        requirement_ids=[],
        rationale="",
    )
    result = check_sentence(s, {"c1": chunk}, CTX)
    assert result.status == "not_verified"
    assert any(f.check == "duration" and f.outcome == "abstain" for f in result.failures)


def test_duration_year_only_with_to_abstains() -> None:
    chunk = _chunk("c1", "Python work (2020 to 2026)")
    s = Sentence(
        id="Q1.S1",
        kind="claim",
        text="6 years of Python experience",
        citations=["c1"],
        requirement_ids=[],
        rationale="",
    )
    result = check_sentence(s, {"c1": chunk}, CTX)
    assert result.status == "not_verified"


def test_extract_orgs_skips_kafka_skill() -> None:
    orgs = extract_orgs("I built streaming pipelines with Kafka.", LEX)
    assert not any(o.lower() == "kafka" for o in orgs)
