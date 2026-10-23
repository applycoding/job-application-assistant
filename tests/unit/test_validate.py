import pytest

from jaa.models import AnswerOut, LLMDraftOut, Question, SentenceOut
from jaa.privacy.outbound import OutboundDraft, OutboundEvidence
from jaa.providers.validate import DraftInvariantError, validate_draft


def test_empty_cover_fails() -> None:
    req = OutboundDraft(
        job_title="t",
        company=None,
        requirements=[],
        questions=[Question(id="Q1", text="q")],
        evidence=[OutboundEvidence(id="c1", section="s", text="t")],
        gap_terms=[],
    )
    out = LLMDraftOut.model_construct(
        answers=[
            AnswerOut(
                question_id="Q1",
                sentences=[
                    SentenceOut(text="x", citations=["c1"], requirement_ids=[], rationale="r")
                ],
            )
        ],
        cover_note=[],
    )
    with pytest.raises(DraftInvariantError):
        validate_draft(out, req)
