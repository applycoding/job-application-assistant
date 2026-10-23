"""Fact extractors for deterministic truth checks."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from jaa.truth.lexicon import SkillLexicon

_NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}

_ORDINAL_RE = re.compile(r"\b(\d+)(?:st|nd|rd|th)\b", re.IGNORECASE)
_NUMERIC_RE = re.compile(r"\b(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?\s*(%|k|m|b)?\b", re.IGNORECASE)
_HYPHEN_NUM_RE = re.compile(r"\b(\d+)\s*-\s*(person|people|member|engineer|analyst)", re.IGNORECASE)
_WORD_NUM_RE = re.compile(
    r"\b(" + "|".join(_NUMBER_WORDS.keys()) + r")\s*-\s*(person|people|member)\b",
    re.IGNORECASE,
)
_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2}|2100)\b")

_DURATION_RE = re.compile(
    r"\b(over|more than)\s+(\d+)\+?\s*years?\b|\b(\d+)\+?\s*years?\b",
    re.IGNORECASE,
)

_ORG_RE = re.compile(
    r"\b(?:at|for|with|joined)\s+([A-Z][A-Za-z0-9&.'\-]+(?:\s+[A-Z][A-Za-z0-9&.'\-]+)*)",
)
_COMPANY_SUFFIX_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9&.'\-]+(?:\s+[A-Z][A-Za-z0-9&.'\-]+)*)\s+"
    r"(?:Inc\.?|LLC|Ltd\.?|Corp\.?|Corporation|GmbH|PLC)\b"
)

_OWNERSHIP_LEMMAS = ("lead", "manage", "own", "build", "architect")
_OWNERSHIP_RE = re.compile(
    r"\b(led|leads|leading|manage|manages|managed|managing|own|owns|owned|owning|"
    r"build|builds|built|building|architect|architects|architected|architecting)\b",
    re.IGNORECASE,
)
_PASSIVE_BY_RE = re.compile(r"\b\w+ed\s+by\b", re.IGNORECASE)

_NEGATION_RE = re.compile(r"\b(no|not|never|without|cannot|can't|none)\b", re.IGNORECASE)

_SKILL_VERSION_RE = re.compile(
    r"\b([A-Za-z#+][A-Za-z0-9+#.]*)\s+v?(\d+\.\d+(?:\.\d+)?)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class NumberMention:
    value: int | float
    raw: str
    unit: str | None = None


@dataclass(frozen=True)
class DurationMention:
    years: int
    raw: str
    strict_more: bool = False
    plus: bool = False


def extract_numbers(text: str, *, exclude_years: bool = True) -> list[NumberMention]:
    years = set(extract_years(text)) if exclude_years else set()
    skill_versions = {v for _, v in extract_skill_versions(text, SkillLexicon({}, "0"))}
    found: list[NumberMention] = []
    seen: set[str] = set()

    def add(raw: str, value: int | float, unit: str | None = None) -> None:
        if raw in seen:
            return
        if exclude_years and isinstance(value, int) and value in years:
            return
        if raw in skill_versions:
            return
        seen.add(raw)
        found.append(NumberMention(value=value, raw=raw, unit=unit))

    for m in _ORDINAL_RE.finditer(text):
        add(m.group(0), int(m.group(1)))

    for m in _HYPHEN_NUM_RE.finditer(text):
        add(m.group(1), int(m.group(1)))

    for m in _WORD_NUM_RE.finditer(text):
        word = m.group(1).lower()
        add(m.group(0), _NUMBER_WORDS[word])

    for m in _NUMERIC_RE.finditer(text):
        whole = m.group(1).replace(",", "")
        if "." in whole and m.group(2):
            val = float(f"{whole}.{m.group(2)}")
        else:
            val = int(whole)
        unit = (m.group(3) or "").lower() or None
        if unit == "%":
            add(m.group(0), val, "%")
        elif unit in ("k", "m", "b"):
            add(m.group(0), val, unit)
        else:
            add(m.group(0), val)

    for word, num in _NUMBER_WORDS.items():
        pat = re.compile(rf"\b{word}\b", re.IGNORECASE)
        for m in pat.finditer(text):
            if f"word:{word}" in seen:
                continue
            seen.add(f"word:{word}")
            found.append(NumberMention(value=num, raw=m.group(0)))

    return found


def extract_years(text: str) -> list[int]:
    return [int(m.group(1)) for m in _YEAR_RE.finditer(text)]


def extract_durations(text: str) -> list[DurationMention]:
    out: list[DurationMention] = []
    for m in _DURATION_RE.finditer(text):
        if m.group(1) in ("over", "more than"):
            years = int(m.group(2))
            out.append(
                DurationMention(years=years, raw=m.group(0), strict_more=True, plus="+" in m.group(0))
            )
        else:
            years = int(m.group(3))
            plus = "+" in m.group(0)
            out.append(DurationMention(years=years, raw=m.group(0), plus=plus))
    return out


def extract_orgs(text: str, lexicon: SkillLexicon) -> list[str]:
    skills = lexicon.find(text)
    orgs: list[str] = []
    for m in _ORG_RE.finditer(text):
        name = m.group(1).strip()
        if name in skills:
            continue
        orgs.append(name)
    for m in _COMPANY_SUFFIX_RE.finditer(text):
        name = m.group(1).strip()
        if name in skills:
            continue
        orgs.append(name)
    return orgs


def extract_ownership(text: str) -> set[str]:
    if _PASSIVE_BY_RE.search(text):
        return set()
    found: set[str] = set()
    for m in _OWNERSHIP_RE.finditer(text):
        word = m.group(0).lower()
        for lemma in _OWNERSHIP_LEMMAS:
            if word.startswith(lemma):
                found.add(lemma)
    return found


def negated_terms(text: str, terms: Iterable[str]) -> set[str]:
    tokens = re.findall(r"[a-z0-9+#.]+", text.lower())
    negated: set[str] = set()
    for i, tok in enumerate(tokens):
        if not _NEGATION_RE.fullmatch(tok):
            continue
        window = tokens[i + 1 : i + 5]
        for term in terms:
            t = term.lower()
            if t in window:
                negated.add(term)
    return negated


def extract_skill_versions(text: str, lexicon: SkillLexicon) -> set[tuple[str, str]]:
    skills = lexicon.find(text)
    pairs: set[tuple[str, str]] = set()
    for m in _SKILL_VERSION_RE.finditer(text):
        skill_raw = m.group(1)
        version = m.group(2)
        for skill in skills:
            if skill.lower() == skill_raw.lower():
                pairs.add((skill, version))
    return pairs


def number_in_text(value: int | float, text: str) -> bool:
    nums = extract_numbers(text, exclude_years=False)
    for n in nums:
        if n.value == value:
            return True
    return str(int(value)) in text if isinstance(value, int) else False
