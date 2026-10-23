"""Deterministic explanations for claims."""

from __future__ import annotations

from collections.abc import Mapping

from jaa.models import Chunk, Explanation, MatchedTerm, Requirement, Sentence
from jaa.retrieval.eligibility import eligible
from jaa.truth.lexicon import SkillLexicon


def explain(
    sentence: Sentence,
    reqs: Mapping[str, Requirement],
    pool: Mapping[str, Chunk],
    lexicon: SkillLexicon | None = None,
) -> Explanation:
    if lexicon is None:
        from jaa.truth.lexicon import load_lexicon

        lexicon = load_lexicon()

    matches: list[MatchedTerm] = []
    for cid in sentence.citations:
        chunk = pool.get(cid)
        if chunk is None:
            continue
        terms: set[str] = set()
        for rid in sentence.requirement_ids:
            req = reqs.get(rid)
            if req is None:
                continue
            for term in eligible(chunk, req, lexicon):
                terms.add(term)
        if terms:
            matches.append(MatchedTerm(chunk_id=cid, terms=sorted(terms)))

    return Explanation(
        requirement_ids=list(sentence.requirement_ids),
        matches=matches,
        model_rationale=sentence.rationale,
    )
