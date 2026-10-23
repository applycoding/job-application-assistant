import pytest

from jaa.models import Question, Sentence, SentenceCheck
from jaa.privacy.outbound import OutboundDraft, OutboundEvidence
from jaa.truth.judge import apply_judge
from tests.support.scripted_provider import ScriptedProvider


@pytest.mark.asyncio
async def test_judge_applied():
    sc = [
        SentenceCheck(
            sentence_id="Q1.S1", status="checks_passed", failures=[], checks_run=[], judge=None
        )
    ]
    claims = [
        Sentence(
            id="Q1.S1",
            kind="claim",
            text="Python work",
            citations=["c1"],
            requirement_ids=[],
            rationale="",
        )
    ]
    outbound = OutboundDraft(
        job_title="t",
        company=None,
        requirements=[],
        questions=[Question(id="Q1", text="q")],
        evidence=[OutboundEvidence(id="c1", section="s", text="python")],
        gap_terms=[],
    )
    provider = ScriptedProvider(
        judges=[{"verdicts": [{"sentence_id": "Q1.S1", "entailed": True, "rationale": "ok"}]}]
    )
    out = await apply_judge(sc, claims, provider, outbound)
    assert out[0].status == "entailed"
