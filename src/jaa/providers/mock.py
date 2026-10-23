"""Deterministic offline mock provider."""

from __future__ import annotations

from collections.abc import Sequence

from jaa.models import AnswerOut, Chunk, JudgeOut, JudgeVerdict, LLMDraftOut, SentenceOut
from jaa.privacy.outbound import OutboundDraft as OutboundDraftModel
from jaa.privacy.outbound import OutboundJudge, OutboundRequirement
from jaa.providers.validate import validate_draft
from jaa.retrieval.bm25 import BM25Ranker
from jaa.retrieval.tokenize import tokenize
from jaa.truth.lexicon import SkillLexicon

INJECTED_CLAIM = "At Initech, I was part of a 15-person platform team."

LEAD_INS = (
    "A relevant example from my CV: {text}.",
    "I can also point to this: {text}.",
    "In addition: {text}.",
)

_LEAD_PHRASES = tuple(s.split("{")[0].strip().lower() for s in LEAD_INS)


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
        used_claims: set[str] = set()

        answers: list[AnswerOut] = []
        for question in req.questions:
            query = tokenize(f"{question.text} {must_text}")
            ranked = _rank_pool(chunks, query)
            sentences: list[SentenceOut] = []
            lead_idx = 0
            for chunk in ranked:
                text = _unique_claim_text(chunk, lex, used_claims, lead_idx)
                if text is None:
                    continue
                lead_idx += 1
                rid = _best_requirement(chunk, req.requirements)
                terms = _matched_terms(chunk, req.requirements)
                req_for_chunk = next((r for r in req.requirements if r.id == rid), None)
                if req_for_chunk is not None:
                    terms = _matched_terms(chunk, [req_for_chunk])
                sentences.append(
                    SentenceOut(
                        text=LEAD_INS[(lead_idx - 1) % 3].format(text=text),
                        citations=[chunk.id],
                        requirement_ids=[rid] if rid and terms else [],
                        rationale=(
                            f"Addresses {rid} using {chunk.id} (matched: {', '.join(terms)})."
                        ),
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

        cover_claims: list[SentenceOut] = []
        for req_item in must_reqs[:4]:
            cover_chunk = _top_chunk_for_requirement(chunks, req_item, req.requirements)
            if cover_chunk is None:
                continue
            if not _matched_terms(cover_chunk, [req_item]):
                continue
            body = _unique_claim_text(cover_chunk, lex, used_claims, 0) or _format_evidence_body(
                cover_chunk, lex
            )
            cover_claims.append(
                SentenceOut(
                    text=f"My background includes: {body}.",
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
    lead_idx: int,
) -> str | None:
    body = _format_evidence_body(chunk, lexicon)
    key = body.lower()
    if key in used:
        return None
    used.add(key)
    if lead_idx == 0:
        return body
    return body[0].lower() + body[1:] if body else body


def _best_requirement(chunk: _PoolChunk, requirements: Sequence[OutboundRequirement]) -> str:
    best_id = ""
    best_count = -1
    chunk_tokens = set(tokenize(chunk.evidence_text))
    for req in requirements:
        overlap = sum(1 for t in _req_tokens(req) if t in chunk_tokens)
        if overlap > best_count or (overlap == best_count and req.id < best_id):
            best_count = overlap
            best_id = req.id
    return best_id


def _matched_terms(chunk: _PoolChunk, requirements: Sequence[OutboundRequirement]) -> list[str]:
    chunk_tokens = set(tokenize(chunk.evidence_text))
    terms: set[str] = set()
    for req in requirements:
        for t in _req_tokens(req):
            if t in chunk_tokens:
                terms.add(t)
    return sorted(terms)


def _req_tokens(req: OutboundRequirement) -> list[str]:
    return tokenize(req.text)


def _top_chunk_for_requirement(
    chunks: Sequence[_PoolChunk],
    req_item: OutboundRequirement,
    all_reqs: Sequence[OutboundRequirement],
) -> _PoolChunk | None:
    query = tokenize(req_item.text)
    ranked = _rank_pool(chunks, query)
    for chunk in ranked:
        if _matched_terms(chunk, [req_item]):
            return chunk
    return ranked[0] if ranked else None


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
            break
    return set(tokenize(claim))
