"""Deterministic offline mock provider."""

from __future__ import annotations

from collections.abc import Sequence

from jaa.models import (
    AnswerOut,
    Chunk,
    JudgeOut,
    JudgeVerdict,
    LLMDraftOut,
    Requirement,
    SentenceOut,
)
from jaa.privacy.outbound import OutboundDraft as OutboundDraftModel
from jaa.privacy.outbound import OutboundJudge, OutboundRequirement
from jaa.providers.validate import validate_draft
from jaa.retrieval.bm25 import BM25Ranker
from jaa.retrieval.eligibility import eligible
from jaa.retrieval.tokenize import tokenize
from jaa.truth.lexicon import SkillLexicon

INJECTED_CLAIM = "At Initech, I was part of a 15-person platform team."

LEAD_INS = (
    "A relevant example from my CV: {text}.",
    "I can also point to this: {text}.",
    "In addition: {text}.",
)

_LEAD_PHRASES = tuple(s.split("{")[0].strip().lower() for s in LEAD_INS)
_COVER_PREFIX = "my background includes:"


class MockProvider:
    name = "mock"
    model = "mock-1"
    judge_model = "mock-judge-1"

    def __init__(self, *, inject_unsupported: bool = True) -> None:
        self._inject_unsupported = inject_unsupported

    async def draft(self, req: OutboundDraftModel) -> LLMDraftOut:
        lex = SkillLexicon.load(None)
        chunks = _chunks_from_outbound(req)
        must_reqs = [r for r in req.requirements if r.priority == "must"]
        must_text = " ".join(r.text for r in must_reqs)
        used_answer_bodies: set[str] = set()
        used_cover_bodies: set[str] = set()
        used_cover_chunks: set[str] = set()

        answers: list[AnswerOut] = []
        for question in req.questions:
            query = tokenize(f"{question.text} {must_text}")
            ranked = _rank_pool(chunks, query)
            sentences: list[SentenceOut] = []
            lead_idx = 0
            for chunk in ranked:
                text = _unique_claim_text(chunk, lex, used_answer_bodies)
                if text is None:
                    continue
                lead_idx += 1
                rid, terms = _pick_requirement_for_chunk(chunk, req.requirements, lex)
                if terms:
                    rationale = f"Addresses {rid} using {chunk.id} (matched: {', '.join(terms)})."
                else:
                    rationale = f"Addresses {rid} using {chunk.id}." if rid else "Evidence from CV."
                sentences.append(
                    SentenceOut(
                        text=LEAD_INS[(lead_idx - 1) % 3].format(text=text),
                        citations=[chunk.id],
                        requirement_ids=[rid] if rid and terms else [],
                        rationale=rationale,
                    )
                )
                if len(sentences) >= 3:
                    break
            if not sentences and ranked:
                chunk = ranked[0]
                body = _format_evidence_body(chunk, lex)
                sentences.append(
                    SentenceOut(
                        text=LEAD_INS[0].format(text=body),
                        citations=[chunk.id],
                        requirement_ids=[],
                        rationale="Fallback sentence for mock draft.",
                    )
                )
            answers.append(AnswerOut(question_id=question.id, sentences=sentences))

        cover_reqs = must_reqs if must_reqs else list(req.requirements)
        cover_claims: list[SentenceOut] = []
        for req_item in cover_reqs:
            if len(cover_claims) >= 3:
                break
            cover_chunk = _top_chunk_for_requirement(chunks, req_item, lex)
            if cover_chunk is None:
                continue
            if not _eligible_terms(cover_chunk, req_item, lex):
                continue
            if cover_chunk.id in used_cover_chunks:
                continue
            used_cover_chunks.add(cover_chunk.id)
            cover_body = _unique_claim_text(cover_chunk, lex, used_cover_bodies)
            if cover_body is None:
                continue
            cover_claims.append(
                SentenceOut(
                    text=f"My background includes: {cover_body}.",
                    citations=[cover_chunk.id],
                    requirement_ids=[req_item.id],
                    rationale=f"Highlights {req_item.id} via {cover_chunk.id}.",
                )
            )

        if self._inject_unsupported and chunks:
            cover_claims.append(
                SentenceOut(
                    text=INJECTED_CLAIM,
                    citations=[chunks[0].id],
                    requirement_ids=[],
                    rationale="Synthetic unsupported claim for demo.",
                )
            )

        out = LLMDraftOut(answers=answers, cover_note=cover_claims or [_fallback_cover(chunks)])
        validate_draft(out, req)
        return out

    async def judge(self, req: OutboundJudge) -> JudgeOut:
        verdicts: list[JudgeVerdict] = []
        for item in req.items:
            claim_tokens = _content_tokens(item.claim)
            ev_tokens: set[str] = set()
            for ev in item.evidence:
                ev_tokens |= set(tokenize(f"{ev.section} {ev.text}"))
            ratio = 1.0 if not claim_tokens else len(claim_tokens & ev_tokens) / len(claim_tokens)
            entailed = ratio >= 0.6
            verdicts.append(
                JudgeVerdict(
                    sentence_id=item.sentence_id,
                    entailed=entailed,
                    rationale=f"Token overlap {ratio:.2f}.",
                )
            )
        return JudgeOut(verdicts=verdicts)


def _chunks_from_outbound(req: OutboundDraftModel) -> list[_PoolChunk]:
    return [_PoolChunk(id=e.id, text=e.text, section=e.section) for e in req.evidence]


class _PoolChunk:
    def __init__(self, id: str, text: str, section: str) -> None:
        self.id = id
        self.text = text
        self.section = section

    @property
    def evidence_text(self) -> str:
        return f"{self.section}\n{self.text}"


def _pool_to_chunk(chunk: _PoolChunk) -> Chunk:
    return Chunk(
        id=chunk.id,
        doc_id="mock",
        line_no=0,
        kind="bullet",
        text=chunk.text,
        section=chunk.section,
    )


def _requirement_from_outbound(req: OutboundRequirement) -> Requirement:
    return Requirement(
        id=req.id,
        text=req.text,
        priority=req.priority,
        skills=list(req.skills),
        terms=list(req.terms),
        min_years=None,
    )


def _eligible_terms(
    chunk: _PoolChunk,
    req: OutboundRequirement,
    lexicon: SkillLexicon,
) -> list[str]:
    return eligible(_pool_to_chunk(chunk), _requirement_from_outbound(req), lexicon)


def _pick_requirement_for_chunk(
    chunk: _PoolChunk,
    requirements: Sequence[OutboundRequirement],
    lexicon: SkillLexicon,
) -> tuple[str, list[str]]:
    best_id = ""
    best_terms: list[str] = []
    for req in requirements:
        terms = _eligible_terms(chunk, req, lexicon)
        if len(terms) > len(best_terms) or (
            len(terms) == len(best_terms) and terms and (not best_id or req.id < best_id)
        ):
            best_id = req.id
            best_terms = terms
    return best_id, best_terms


def _rank_pool(chunks: Sequence[_PoolChunk], query: list[str]) -> list[_PoolChunk]:
    if not chunks:
        return []
    pseudo = [
        Chunk(
            id=c.id,
            doc_id="mock",
            line_no=0,
            kind="bullet",
            text=c.text,
            section=c.section,
        )
        for c in chunks
    ]
    ranker = BM25Ranker(pseudo)
    scores = ranker.score(query, [c.id for c in chunks])
    return sorted(chunks, key=lambda c: (-scores[c.id], c.id))


def _format_evidence_body(chunk: _PoolChunk, lexicon: SkillLexicon) -> str:
    skills = lexicon.find(chunk.text)
    if skills:
        return ", ".join(sorted(skills, key=str.casefold))
    return chunk.text.rstrip(".")


def _unique_claim_text(
    chunk: _PoolChunk,
    lexicon: SkillLexicon,
    used: set[str],
) -> str | None:
    body = _format_evidence_body(chunk, lexicon)
    key = body.lower()
    if key in used:
        return None
    used.add(key)
    return body


def _top_chunk_for_requirement(
    chunks: Sequence[_PoolChunk],
    req_item: OutboundRequirement,
    lexicon: SkillLexicon,
) -> _PoolChunk | None:
    query = tokenize(req_item.text)
    ranked = _rank_pool(chunks, query)
    for chunk in ranked:
        if _eligible_terms(chunk, req_item, lexicon):
            return chunk
    return None


def _fallback_cover(chunks: Sequence[_PoolChunk]) -> SentenceOut:
    cid = chunks[0].id if chunks else "none"
    return SentenceOut(
        text="I am enthusiastic about this opportunity.",
        citations=[cid] if chunks else [],
        requirement_ids=[],
        rationale="Fallback cover claim.",
    )


def _content_tokens(claim: str) -> set[str]:
    lower = claim.lower()
    for prefix in _LEAD_PHRASES:
        if lower.startswith(prefix):
            claim = claim[len(prefix) :].lstrip(" :")
            lower = claim.lower()
            break
    if lower.startswith(_COVER_PREFIX):
        claim = claim[len(_COVER_PREFIX) :].lstrip(" :")
    return set(tokenize(claim.rstrip(" .")))
