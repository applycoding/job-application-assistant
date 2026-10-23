"""Server-side draft and judge invariants."""

from __future__ import annotations

from jaa.models import AnswerOut, JudgeOut, LLMDraftOut
from jaa.privacy.outbound import OutboundDraft, OutboundJudge


class DraftInvariantError(ValueError):
    """Raised when model output violates business invariants."""


def validate_draft(out: LLMDraftOut, req: OutboundDraft) -> None:
    q_ids = [q.id for q in req.questions]
    if len(out.answers) != len(q_ids):
        raise DraftInvariantError(
            f"answers must cover exactly {len(q_ids)} questions, got {len(out.answers)}"
        )
    seen_q: set[str] = set()
    for ans in out.answers:
        if ans.question_id not in q_ids:
            raise DraftInvariantError(f"unknown question_id: {ans.question_id}")
        if ans.question_id in seen_q:
            raise DraftInvariantError(f"duplicate question_id: {ans.question_id}")
        seen_q.add(ans.question_id)
        if not (1 <= len(ans.sentences) <= req.max_sentences_per_answer):
            raise DraftInvariantError("sentence count out of bounds for answer")
        _check_sentences(ans.sentences, req)

    if not out.cover_note:
        raise DraftInvariantError("cover_note must not be empty")
    if len(out.cover_note) > req.max_cover_claims:
        raise DraftInvariantError("cover_note exceeds max_cover_claims")
    _check_sentences(out.cover_note, req)

    if seen_q != set(q_ids):
        raise DraftInvariantError("missing question ids in answers")


def _check_sentences(sentences: list, req: OutboundDraft) -> None:
    pool_ids = {e.id for e in req.evidence}
    for sent in sentences:
        if len(sent.citations) > 4:
            raise DraftInvariantError("too many citations")
        if len(sent.requirement_ids) > 5:
            raise DraftInvariantError("too many requirement_ids")
        if len(set(sent.citations)) != len(sent.citations):
            raise DraftInvariantError("duplicate citation in sentence")
        for cid in sent.citations:
            if cid not in pool_ids:
                raise DraftInvariantError(f"citation not in evidence pool: {cid}")


def validate_judge(out: JudgeOut, req: OutboundJudge) -> None:
    expected = [item.sentence_id for item in req.items]
    got = [v.sentence_id for v in out.verdicts]
    if len(got) != len(expected):
        raise DraftInvariantError(
            f"verdicts must cover exactly {len(expected)} items, got {len(got)}"
        )
    if set(got) != set(expected):
        raise DraftInvariantError("verdict sentence_ids must match request exactly once")
    if len(got) != len(set(got)):
        raise DraftInvariantError("duplicate sentence_id in verdicts")
