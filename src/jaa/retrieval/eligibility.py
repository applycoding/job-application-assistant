from __future__ import annotations

import re

from jaa.models import Chunk, Requirement
from jaa.retrieval.tokenize import tokenize
from jaa.truth.lexicon import CASE_SENSITIVE_SKILLS, SkillLexicon

_SKILL_TERM_TRAIL = r"(?![A-Za-z0-9+#])"


def _term_in_chunk(term: str, chunk: Chunk, lexicon: SkillLexicon) -> bool:
    if term in lexicon.skill_names:
        return term in lexicon.find(chunk.text) or term in lexicon.find(chunk.section)
    if term in CASE_SENSITIVE_SKILLS:
        pattern = rf"(?<![A-Za-z0-9+#.]){term}{_SKILL_TERM_TRAIL}"
        return bool(re.search(pattern, chunk.evidence_text))
    tokens = tokenize(chunk.evidence_text)
    return term.lower() in tokens


def eligible(chunk: Chunk, req: Requirement, lexicon: SkillLexicon) -> list[str]:
    matched: list[str] = []
    for term in req.terms:
        if _term_in_chunk(term, chunk, lexicon):
            matched.append(term)
    return matched
