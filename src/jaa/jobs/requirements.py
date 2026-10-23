from __future__ import annotations

import re
from collections.abc import Mapping

from jaa.models import Requirement
from jaa.retrieval.tokenize import tokenize
from jaa.truth.lexicon import SkillLexicon

SECTION_MUST = ("requirements", "what you'll bring", "must have", "qualifications", "about you")
SECTION_NICE = ("nice to have", "bonus", "preferred")

DEFAULT_QUESTION = "What relevant experience do you bring to this role?"

GENERIC_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "have",
        "in",
        "including",
        "is",
        "minimum",
        "of",
        "on",
        "or",
        "plus",
        "preferred",
        "proficient",
        "required",
        "the",
        "to",
        "using",
        "with",
        "ability",
        "demonstrated",
        "excellent",
        "experience",
        "knowledge",
        "proven",
        "strong",
        "understanding",
        "working",
        "years",
        "year",
        "yrs",
        "yr",
    }
)

_MIN_YEARS_RE = re.compile(
    r"(?:\b(?:at\s+)?least\s+)?(\d{1,2})\s*\+?\s*(?:years?|yrs?)\b",
    re.IGNORECASE,
)
_BULLET_RE = re.compile(r"^[\s]*(?:[-*•]|\d+[.)])\s+")
_FALLBACK_SENTENCE_RE = re.compile(
    r"\b(?:must|should|experience|proficient)\b",
    re.IGNORECASE,
)


def extract_min_years(text: str) -> int | None:
    match = _MIN_YEARS_RE.search(text)
    if not match:
        return None
    return int(match.group(1))


def requirement_terms(text: str, skills: list[str]) -> list[str]:
    if skills:
        return list(skills)
    tokens = tokenize(text)
    terms: list[str] = []
    seen: set[str] = set()
    for tok in tokens:
        if tok in GENERIC_WORDS or tok in seen:
            continue
        seen.add(tok)
        terms.append(tok)
    return terms


def _line_to_requirement(
    line: str,
    priority: str,
    rid: str,
    lexicon: SkillLexicon,
) -> Requirement | None:
    cleaned = line.strip()
    if not cleaned:
        return None
    cleaned = _BULLET_RE.sub("", cleaned).strip()
    if not cleaned:
        return None
    skills = lexicon.skills_in_text_ordered(cleaned)
    terms = requirement_terms(cleaned, skills)
    if not terms and not skills:
        return None
    return Requirement(
        id=rid,
        text=cleaned,
        priority="must" if priority == "must" else "nice",
        skills=skills,
        terms=terms,
        min_years=extract_min_years(cleaned),
    )


def extract_requirements(
    sections: Mapping[str, list[str]],
    full_text: str,
    lexicon: SkillLexicon,
) -> list[Requirement]:
    requirements: list[Requirement] = []
    counter = 1

    def add_lines(lines: list[str], priority: str) -> None:
        nonlocal counter
        for line in lines:
            rid = f"R{counter}"
            req = _line_to_requirement(line, priority, rid, lexicon)
            if req is None:
                continue
            requirements.append(req)
            counter += 1

    for key in SECTION_MUST:
        if key in sections:
            add_lines(list(sections[key]), "must")
    for key in SECTION_NICE:
        if key in sections:
            add_lines(list(sections[key]), "nice")

    if requirements:
        return requirements

    lines = full_text.splitlines()
    bullets = [ln for ln in lines if _BULLET_RE.match(ln)]
    if bullets:
        add_lines(bullets, "must")
        if requirements:
            return requirements

    sentences = re.split(r"(?<=[.!?])\s+", full_text.replace("\n", " "))
    for sentence in sentences:
        if _FALLBACK_SENTENCE_RE.search(sentence):
            rid = f"R{counter}"
            req = _line_to_requirement(sentence.strip(), "must", rid, lexicon)
            if req is None:
                continue
            requirements.append(req)
            counter += 1
    if requirements:
        return requirements

    for skill in lexicon.skills_in_text_ordered(full_text):
        text = f"Skill: {skill}"
        requirements.append(
            Requirement(
                id=f"R{counter}",
                text=text,
                priority="must",
                skills=[skill],
                terms=[skill],
                min_years=None,
            )
        )
        counter += 1

    return requirements
