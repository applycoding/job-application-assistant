"""Assemble model output into drafts with ids and framing."""

from __future__ import annotations

from collections.abc import Mapping

from jaa.generation.templates import FRAMING_TEMPLATES
from jaa.models import (
    AnswerDraft,
    Chunk,
    CoverNote,
    Drafts,
    JobPost,
    LLMDraftOut,
    Sentence,
)
from jaa.truth.lexicon import SkillLexicon


def assemble_drafts(
    out: LLMDraftOut,
    job: JobPost,
    pool: Mapping[str, Chunk],
    lexicon: SkillLexicon,
) -> tuple[Drafts, list[str]]:
    warnings: list[str] = []
    req_ids = {r.id for r in job.requirements}
    q_map = {q.id: q for q in job.questions}

    answers: list[AnswerDraft] = []
    for ans_out in out.answers:
        q = q_map.get(ans_out.question_id)
        question_text = q.text if q else ""
        sentences: list[Sentence] = []
        for i, sent in enumerate(ans_out.sentences, start=1):
            rid_warn = _filter_requirement_ids(sent.requirement_ids, req_ids, warnings)
            sentences.append(
                Sentence(
                    id=f"{ans_out.question_id}.S{i}",
                    kind="claim",
                    text=sent.text,
                    citations=list(sent.citations),
                    requirement_ids=rid_warn,
                    rationale=sent.rationale,
                )
            )
        answers.append(
            AnswerDraft(
                question_id=ans_out.question_id,
                question=question_text,
                sentences=sentences,
            )
        )

    open_key = "open" if job.company else "open_nocompany"
    open_text = (
        FRAMING_TEMPLATES["open"].format(title=job.title, company=job.company)
        if job.company
        else FRAMING_TEMPLATES["open_nocompany"].format(title=job.title)
    )
    salutation = "Dear Hiring Team," if not job.company else f"Dear {job.company} Team,"

    cover_sentences: list[Sentence] = [
        Sentence(
            id="C.F1",
            kind="framing",
            text=open_text,
            template_id=open_key,
        )
    ]
    for i, sent in enumerate(out.cover_note, start=1):
        rid_warn = _filter_requirement_ids(sent.requirement_ids, req_ids, warnings)
        cover_sentences.append(
            Sentence(
                id=f"C.S{i}",
                kind="claim",
                text=sent.text,
                citations=list(sent.citations),
                requirement_ids=rid_warn,
                rationale=sent.rationale,
            )
        )
    cover_sentences.append(
        Sentence(
            id="C.F2",
            kind="framing",
            text=FRAMING_TEMPLATES["close"],
            template_id="close",
        )
    )

    cover = CoverNote(
        salutation=salutation,
        sentences=cover_sentences,
        signoff="Kind regards,\nAlex Doe",
    )
    return Drafts(answers=answers, cover_note=cover), warnings


def _filter_requirement_ids(
    ids: list[str],
    valid: set[str],
    warnings: list[str],
) -> list[str]:
    out: list[str] = []
    for rid in ids:
        if rid in valid:
            out.append(rid)
        elif rid:
            warnings.append(f"Unknown requirement id dropped: {rid}")
    return out
