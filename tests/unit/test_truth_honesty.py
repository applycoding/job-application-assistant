"""Honesty regressions from independent verification."""

from datetime import date

from jaa.models import Chunk, Sentence
from jaa.truth.deterministic import CheckContext, check_sentence
from jaa.truth.extractors import extract_orgs, extract_ownership, negated_terms
from jaa.truth.lexicon import SkillLexicon

REF = date(2026, 10, 23)
LEX = SkillLexicon.load(None)


def test_negation_with_trailing_period_on_term() -> None:
    evidence = "No production experience with Kubernetes."
    claim = "I have production experience with Kubernetes."
    assert "kubernetes" in negated_terms(evidence, ["kubernetes"])
    assert "kubernetes" not in negated_terms(claim, ["kubernetes"])


def test_negation_never_used_vs_positive_evidence() -> None:
    claim = "I have never used Kubernetes."
    evidence = "Ran Kubernetes in production."
    assert "kubernetes" in negated_terms(claim, ["kubernetes"])
    assert "kubernetes" not in negated_terms(evidence, ["kubernetes"])


def test_ownership_led_active_not_wiped_by_passive_clause() -> None:
    assert "lead" in extract_ownership("I led the migration.")
    assert extract_ownership("Supported a migration led by another team.") == set()


def test_mixed_citations_team_size() -> None:
    ctx = CheckContext(lexicon=LEX, reference_date=REF, target_company=None)
    c1 = Chunk(
        id="c1",
        doc_id="d",
        line_no=1,
        kind="bullet",
        text="Worked with 15 analysts.",
        section="Exp",
    )
    c2 = Chunk(
        id="c2",
        doc_id="d",
        line_no=2,
        kind="bullet",
        text="Led a team of 2.",
        section="Exp",
    )
    s = Sentence(
        id="Q1.S1",
        kind="claim",
        text="I led a team of 15 analysts.",
        citations=["c1", "c2"],
        requirement_ids=[],
        rationale="",
    )
    result = check_sentence(s, {"c1": c1, "c2": c2}, ctx)
    assert result.status == "unsupported"
    assert any(f.check == "mixed_citations" for f in result.failures)


def test_duration_year_only_span_not_verified() -> None:
    ctx = CheckContext(lexicon=LEX, reference_date=REF, target_company=None)
    chunk = Chunk(
        id="c1",
        doc_id="d",
        line_no=1,
        kind="bullet",
        text="Python work (2020 – 2026)",
        section="Skills",
    )
    s = Sentence(
        id="Q1.S1",
        kind="claim",
        text="6 years of Python experience",
        citations=["c1"],
        requirement_ids=[],
        rationale="",
    )
    result = check_sentence(s, {"c1": chunk}, ctx)
    assert result.status == "not_verified"
    assert any(f.check == "duration" and f.outcome == "abstain" for f in result.failures)


def test_extract_orgs_skips_kafka_with_trailing_period() -> None:
    orgs = extract_orgs("We use Kafka. for streaming.", LEX)
    assert not any(o.lower().startswith("kafka") for o in orgs)
