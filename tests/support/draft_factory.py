"""Build minimal LLMDraftOut payloads for ScriptedProvider tests."""

from __future__ import annotations

from jaa.models import AnswerOut, LLMDraftOut, SentenceOut
from jaa.privacy.outbound import OutboundDraft


def minimal_draft(
    req: OutboundDraft,
    *,
    claim_text: str,
    citation_id: str | None = None,
) -> LLMDraftOut:
    cid = citation_id or req.evidence[0].id
    sentence = SentenceOut(
        text=claim_text,
        citations=[cid],
        requirement_ids=[req.requirements[0].id] if req.requirements else [],
        rationale="scripted",
    )
    answers = [
        AnswerOut(question_id=q.id, sentences=[sentence] if i == 0 else [sentence])
        for i, q in enumerate(req.questions)
    ]
    cover = SentenceOut(
        text="Cover claim for testing.",
        citations=[cid],
        requirement_ids=[],
        rationale="scripted",
    )
    return LLMDraftOut(
        answers=answers,
        cover_note=[cover],
    )
