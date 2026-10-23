import pytest

from jaa.models import AnswerOut, JudgeOut, JudgeVerdict, LLMDraftOut, Question, SentenceOut
from jaa.privacy.outbound import JudgeItem, OutboundDraft, OutboundEvidence, OutboundJudge
from jaa.providers.validate import DraftInvariantError, validate_draft, validate_judge


def _outbound() -> OutboundDraft:
    return OutboundDraft(
        job_title="t",
        company=None,
        requirements=[],
        questions=[Question(id="Q1", text="q")],
        evidence=[OutboundEvidence(id="e1", section="s", text="evidence line here")],
        gap_terms=[],
        max_sentences_per_answer=3,
        max_cover_claims=5,
    )


def _sentence(**kwargs: object) -> SentenceOut:
    defaults = {
        "text": "claim",
        "citations": ["e1"],
        "requirement_ids": [],
        "rationale": "r",
    }
    defaults.update(kwargs)
    return SentenceOut(**defaults)  # type: ignore[arg-type]


def test_wrong_answer_count() -> None:
    req = _outbound()
    out = LLMDraftOut.model_construct(answers=[], cover_note=[_sentence()])
    with pytest.raises(DraftInvariantError, match="answers must cover"):
        validate_draft(out, req)


def test_unknown_question_id() -> None:
    req = _outbound()
    out = LLMDraftOut(
        answers=[AnswerOut(question_id="Q9", sentences=[_sentence()])],
        cover_note=[_sentence()],
    )
    with pytest.raises(DraftInvariantError, match="unknown question_id"):
        validate_draft(out, req)


def test_duplicate_question_id() -> None:
    req = OutboundDraft(
        job_title="t",
        company=None,
        requirements=[],
        questions=[
            Question(id="Q1", text="a"),
            Question(id="Q2", text="b"),
        ],
        evidence=[OutboundEvidence(id="e1", section="s", text="evidence line here")],
        gap_terms=[],
    )
    ans = AnswerOut(question_id="Q1", sentences=[_sentence()])
    out = LLMDraftOut.model_construct(answers=[ans, ans], cover_note=[_sentence()])
    with pytest.raises(DraftInvariantError, match="duplicate question_id"):
        validate_draft(out, req)


def test_sentence_count_bounds() -> None:
    req = _outbound()
    out = LLMDraftOut.model_construct(
        answers=[AnswerOut.model_construct(question_id="Q1", sentences=[])],
        cover_note=[_sentence()],
    )
    with pytest.raises(DraftInvariantError, match="sentence count"):
        validate_draft(out, req)


def test_empty_cover_note() -> None:
    req = _outbound()
    out = LLMDraftOut.model_construct(
        answers=[AnswerOut(question_id="Q1", sentences=[_sentence()])],
        cover_note=[],
    )
    with pytest.raises(DraftInvariantError, match="cover_note must not be empty"):
        validate_draft(out, req)


def test_citation_not_in_pool() -> None:
    req = _outbound()
    out = LLMDraftOut(
        answers=[AnswerOut(question_id="Q1", sentences=[_sentence(citations=["nope"])])],
        cover_note=[_sentence()],
    )
    with pytest.raises(DraftInvariantError, match="citation not in evidence pool"):
        validate_draft(out, req)


def test_judge_verdict_count() -> None:
    req = OutboundJudge(items=[JudgeItem(sentence_id="S1", claim="c", evidence=[])])
    out = JudgeOut(verdicts=[])
    with pytest.raises(DraftInvariantError, match="verdicts must cover"):
        validate_judge(out, req)


def test_judge_duplicate_sentence_id() -> None:
    req = OutboundJudge(
        items=[
            JudgeItem(sentence_id="S1", claim="c", evidence=[]),
            JudgeItem(sentence_id="S2", claim="d", evidence=[]),
        ]
    )
    out = JudgeOut(
        verdicts=[
            JudgeVerdict(sentence_id="S1", entailed=True, rationale=""),
            JudgeVerdict(sentence_id="S1", entailed=False, rationale=""),
        ]
    )
    with pytest.raises(DraftInvariantError, match="match request exactly once"):
        validate_judge(out, req)
