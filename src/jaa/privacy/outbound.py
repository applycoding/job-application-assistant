from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, Field

from jaa.models import JobPost, Question, RetrievalResult, Sentence
from jaa.privacy.redact import redact


class OutboundEvidence(BaseModel):
    id: str
    section: str
    text: str


class OutboundRequirement(BaseModel):
    id: str
    text: str
    priority: Literal["must", "nice"]


class OutboundDraft(BaseModel):
    job_title: str
    company: str | None
    requirements: list[OutboundRequirement]
    questions: list[Question]
    evidence: list[OutboundEvidence]
    gap_terms: list[str]
    max_sentences_per_answer: int = 5
    max_cover_claims: int = 6


class JudgeItem(BaseModel):
    sentence_id: str
    claim: str
    evidence: list[OutboundEvidence]


class OutboundJudge(BaseModel):
    items: list[JudgeItem] = Field(default_factory=list)


def build_outbound_draft(job: JobPost, result: RetrievalResult) -> OutboundDraft:
    evidence = [
        OutboundEvidence(
            id=item.chunk.id,
            section=redact(item.chunk.section),
            text=redact(item.chunk.text),
        )
        for item in result.evidence
    ]
    requirements = [
        OutboundRequirement(
            id=req.id,
            text=redact(req.text),
            priority=req.priority,
        )
        for req in job.requirements
    ]
    questions = [Question(id=q.id, text=redact(q.text)[:500]) for q in job.questions]
    gap_terms = sorted({g.term for g in result.gaps if g.term is not None})
    return OutboundDraft(
        job_title=redact(job.title),
        company=redact(job.company) if job.company else None,
        requirements=requirements,
        questions=questions,
        evidence=evidence,
        gap_terms=gap_terms,
    )


def build_outbound_judge(
    claims: Sequence[Sentence],
    draft: OutboundDraft,
) -> OutboundJudge:
    pool = {item.id: item for item in draft.evidence}
    items: list[JudgeItem] = []
    for sentence in claims:
        cited = [pool[cid] for cid in sentence.citations if cid in pool]
        items.append(
            JudgeItem(
                sentence_id=sentence.id,
                claim=redact(sentence.text),
                evidence=cited,
            )
        )
    return OutboundJudge(items=items)
