"""Mock provider determinism and injected claim."""

from datetime import date

import pytest

from jaa.models import Chunk, Question, Sentence
from jaa.privacy.outbound import JudgeItem, OutboundDraft, OutboundEvidence, OutboundRequirement
from jaa.providers.mock import INJECTED_CLAIM, MockProvider
from jaa.truth.deterministic import CheckContext, check_sentence
from jaa.truth.lexicon import SkillLexicon


def _minimal_outbound() -> OutboundDraft:
    ev = OutboundEvidence(
        id="doc:abc",
        section="Experience > Northwind",
        text="Led Spark pipelines on AWS for 8 years.",
    )
    return OutboundDraft(
        job_title="Role",
        company="Acme",
        requirements=[
            OutboundRequirement(id="R1", text="Python", priority="must"),
        ],
        questions=[Question(id="Q1", text="Experience?")],
        evidence=[ev],
        gap_terms=[],
        max_sentences_per_answer=5,
        max_cover_claims=6,
    )


@pytest.mark.asyncio
async def test_mock_deterministic() -> None:
    p = MockProvider()
    a = await p.draft(_minimal_outbound())
    b = await p.draft(_minimal_outbound())
    assert a.model_dump() == b.model_dump()


@pytest.mark.asyncio
async def test_injected_claim_present() -> None:
    out = await MockProvider().draft(_minimal_outbound())
    texts = [s.text for s in out.cover_note]
    assert INJECTED_CLAIM in texts


@pytest.mark.asyncio
async def test_inject_unsupported_false() -> None:
    out = await MockProvider(inject_unsupported=False).draft(_minimal_outbound())
    assert INJECTED_CLAIM not in [s.text for s in out.cover_note]


@pytest.mark.asyncio
async def test_judge_threshold() -> None:
    p = MockProvider()
    draft = await p.draft(_minimal_outbound())
    from jaa.privacy.outbound import OutboundJudge

    judge_req = OutboundJudge(
        items=[
            JudgeItem(
                sentence_id="C.S1",
                claim=draft.cover_note[0].text,
                evidence=_minimal_outbound().evidence,
            )
        ]
    )
    out = await p.judge(judge_req)
    assert out.verdicts[0].entailed in (True, False)


def test_injected_claim_check_failures() -> None:
    lex = SkillLexicon.load(None)
    pool = {
        "doc:abc": Chunk(
            id="doc:abc",
            doc_id="d1",
            line_no=1,
            kind="bullet",
            text="Worked at Northwind Analytics on Spark.",
            section="Experience > Northwind",
        )
    }
    sent = Sentence(
        id="C.S9",
        kind="claim",
        text=INJECTED_CLAIM,
        citations=["doc:abc"],
        requirement_ids=["R1"],
        rationale="demo",
    )
    ctx = CheckContext(lexicon=lex, reference_date=date(2026, 10, 23), target_company="Acme")
    check = check_sentence(sent, pool, ctx)
    assert check.status == "unsupported"
    checks = {(f.check, f.token) for f in check.failures}
    assert ("employer", "Initech") in checks or any(
        f.check == "employer" and "Initech" in (f.token or "") for f in check.failures
    )
    assert any(f.check == "number" for f in check.failures)
