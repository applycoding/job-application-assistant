"""Gap-term truth checks (lexicon skills only)."""

from datetime import date

import pytest

from jaa.models import Chunk, Sentence
from jaa.truth.deterministic import CheckContext, check_sentence
from jaa.truth.lexicon import SkillLexicon

REF = date(2026, 10, 23)
LEX = SkillLexicon.load(None)
CTX = CheckContext(lexicon=LEX, reference_date=REF, target_company=None)


def _chunk(text: str) -> Chunk:
    return Chunk(
        id="c1",
        doc_id="d",
        line_no=1,
        kind="bullet",
        text=text,
        section="Skills",
    )


def _claim(text: str) -> Sentence:
    return Sentence(
        id="Q1.S1",
        kind="claim",
        text=text,
        citations=["c1"],
        requirement_ids=[],
        rationale="",
    )


def test_go_in_good_does_not_fail() -> None:
    c = _chunk("Python and SQL in production.")
    s = _claim("I am a good engineer who joined two years ago.")
    ctx = CheckContext(
        lexicon=LEX, reference_date=REF, target_company=None, gap_terms=frozenset({"Go"})
    )
    r = check_sentence(s, {"c1": c}, ctx)
    assert not any(f.token == "Go" for f in r.failures)


def test_go_not_in_google_cloud() -> None:
    c = _chunk("Python and SQL in production.")
    s = _claim("I worked with Google Cloud.")
    ctx = CheckContext(
        lexicon=LEX, reference_date=REF, target_company=None, gap_terms=frozenset({"Go"})
    )
    r = check_sentence(s, {"c1": c}, ctx)
    assert not any(f.token == "Go" for f in r.failures)


def test_gap_go_claim_fails_with_gap_detail() -> None:
    c = _chunk("Python APIs only.")
    s = _claim("I have shipped production Go microservices.")
    ctx = CheckContext(
        lexicon=LEX, reference_date=REF, target_company=None, gap_terms=frozenset({"Go"})
    )
    r = check_sentence(s, {"c1": c}, ctx)
    assert any(
        f.check == "skill" and f.token == "Go" and "gap term" in f.detail for f in r.failures
    )


def test_gap_check_disabled_via_empty_gap_terms(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _chunk("Python APIs only.")
    s = _claim("I have shipped production Go microservices.")
    ctx_with = CheckContext(
        lexicon=LEX, reference_date=REF, target_company=None, gap_terms=frozenset({"Go"})
    )
    ctx_without = CheckContext(
        lexicon=LEX, reference_date=REF, target_company=None, gap_terms=frozenset()
    )
    r_with = check_sentence(s, {"c1": c}, ctx_with)
    r_without = check_sentence(s, {"c1": c}, ctx_without)
    assert any("gap term" in f.detail for f in r_with.failures)
    assert not any("gap term" in f.detail for f in r_without.failures)


def test_dot_net_aliases() -> None:
    text = "Built APIs with ASP.NET Core and dotnet libraries."
    found = LEX.find(text)
    assert ".NET" in found


def test_outbound_gap_terms_exclude_generic_req_terms(
    app, settings, repo, fixed_clock, seq_ids
) -> None:
    from jaa.privacy.outbound import build_outbound_draft
    from jaa.retrieval.service import retrieve_for_job
    from jaa.samples import seed

    seed(repo, settings, fixed_clock, seq_ids, app.state.lexicon)
    job = next(j for j in repo.list_jobs() if "Vandelay" in (j.company or ""))
    chunks = repo.get_chunks(retrievable_only=True)
    outbound = build_outbound_draft(job, retrieve_for_job(job, chunks, app.state.lexicon))
    generic = {"tests", "writing", "logging", "structured", "automated", "participating"}
    assert not generic.intersection(outbound.gap_terms)
    assert "Go" in outbound.gap_terms
