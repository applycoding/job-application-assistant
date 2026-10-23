from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from jaa.limits import K_PER_REQ, POOL_MAX
from jaa.models import Chunk, EvidenceItem, Gap, JobPost, RetrievalResult
from jaa.retrieval.bm25 import BM25Ranker
from jaa.retrieval.eligibility import eligible
from jaa.retrieval.tokenize import tokenize
from jaa.truth.lexicon import SkillLexicon


def _query_tokens(req_text: str, skills: list[str]) -> list[str]:
    tokens = tokenize(req_text)
    for skill in skills:
        tokens.extend(tokenize(skill))
    return tokens


def _compute_gaps(
    job: JobPost,
    pool_chunks: Sequence[Chunk],
    lexicon: SkillLexicon,
) -> list[Gap]:
    gaps: list[Gap] = []
    for req in job.requirements:
        covered: set[str] = set()
        for chunk in pool_chunks:
            covered.update(eligible(chunk, req, lexicon))
        if not covered:
            gaps.append(Gap(requirement_id=req.id, term=None))
            continue
        for term in req.terms:
            if term not in covered:
                gaps.append(Gap(requirement_id=req.id, term=term))
    return gaps


def retrieve_for_job(
    job: JobPost,
    chunks: Sequence[Chunk],
    lexicon: SkillLexicon,
) -> RetrievalResult:
    chunk_list = list(chunks)
    if not chunk_list:
        gaps = [Gap(requirement_id=req.id, term=None) for req in job.requirements]
        return RetrievalResult(evidence=[], gaps=gaps)

    ranker = BM25Ranker(chunk_list)
    chunk_by_id = {c.id: c for c in chunk_list}

    pool_scores: dict[str, float] = {}
    pool_req_ids: dict[str, list[str]] = defaultdict(list)
    pool_matched: dict[str, set[str]] = defaultdict(set)

    for req in job.requirements:
        eligible_rows: list[tuple[Chunk, list[str]]] = []
        for chunk in chunk_list:
            matched = eligible(chunk, req, lexicon)
            if matched:
                eligible_rows.append((chunk, matched))

        if not eligible_rows:
            continue

        query = _query_tokens(req.text, req.skills)
        scored: list[tuple[Chunk, list[str], float]] = []
        for chunk, matched in eligible_rows:
            score = ranker.score(query, [chunk.id])[chunk.id]
            scored.append((chunk, matched, score))
        scored.sort(key=lambda row: (-row[2], row[0].id))

        selected: list[str] = []
        selected_set: set[str] = set()

        for term in req.terms:
            for chunk, matched, _score in scored:
                if term not in matched:
                    continue
                if chunk.id not in selected_set:
                    selected.append(chunk.id)
                    selected_set.add(chunk.id)
                break

        for chunk, _matched, _score in scored:
            if len(selected) >= K_PER_REQ:
                break
            if chunk.id in selected_set:
                continue
            selected.append(chunk.id)
            selected_set.add(chunk.id)

        for chunk_id in selected_set:
            chunk = chunk_by_id[chunk_id]
            matched = eligible(chunk, req, lexicon)
            score = ranker.score(query, [chunk_id])[chunk_id]
            prev = pool_scores.get(chunk_id, float("-inf"))
            if score > prev or chunk_id not in pool_scores:
                pool_scores[chunk_id] = score
            if req.id not in pool_req_ids[chunk_id]:
                pool_req_ids[chunk_id].append(req.id)
            pool_matched[chunk_id].update(matched)

    pool_ids = sorted(pool_scores.keys(), key=lambda cid: (-pool_scores[cid], cid))
    pool_ids = pool_ids[:POOL_MAX]

    pool_chunks = [chunk_by_id[cid] for cid in pool_ids]
    gaps = _compute_gaps(job, pool_chunks, lexicon)

    evidence = [
        EvidenceItem(
            chunk=chunk_by_id[cid],
            score=pool_scores[cid],
            requirement_ids=sorted(pool_req_ids[cid]),
            matched_terms=sorted(pool_matched[cid]),
        )
        for cid in pool_ids
    ]

    return RetrievalResult(evidence=evidence, gaps=gaps)
