from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import defaultdict
from collections.abc import Sequence

from jaa.clock import Clock
from jaa.jobs.requirements import (
    DEFAULT_QUESTION,
    SECTION_MUST,
    SECTION_NICE,
    extract_requirements,
)
from jaa.limits import MAX_JOB_CHARS, MAX_QUESTIONS, MAX_REQUIREMENTS
from jaa.models import JobPost, Question
from jaa.truth.lexicon import SkillLexicon

SECTION_QUESTIONS = ("application questions", "questions")

_HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$")
_COMPANY_SUFFIX_RE = re.compile(
    r"\b(?:Inc\.?|LLC|Ltd\.?|Corp\.?|Corporation|Company|Co\.?|GmbH|PLC)\b",
    re.IGNORECASE,
)
_COMPANY_LABEL_RE = re.compile(r"^(?:company|employer|organization)\s*:\s*(.+)$", re.IGNORECASE)
_AT_COMPANY_RE = re.compile(
    r"\b(?:at|@)\s+([A-Z][A-Za-z0-9&'.,\-\s]{1,80}?)(?:\s*[-–—|]|$)",
)
_QUESTION_PREFIX_RE = re.compile(r"^(?:Q\d+[:.)]?\s*|\d+[.)]\s*)", re.IGNORECASE)


class JobParseError(ValueError):
    pass


def _normalize_job_text(text: str) -> str:
    return unicodedata.normalize("NFKC", text).strip()


def _normalize_heading(line: str) -> str:
    raw = line.strip()
    m = _HEADING_RE.match(raw)
    if m:
        raw = m.group(1)
    raw = raw.strip().strip(":").strip()
    return unicodedata.normalize("NFKC", raw).casefold()


def _match_section(norm_heading: str) -> str | None:
    for key in SECTION_MUST:
        if key in norm_heading or norm_heading in key:
            return key
    for key in SECTION_NICE:
        if key in norm_heading or norm_heading in key:
            return key
    for key in SECTION_QUESTIONS:
        if key in norm_heading or norm_heading in key:
            return key
    return None


def _is_section_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if _HEADING_RE.match(stripped):
        return True
    if stripped.endswith(":") and len(stripped) < 80:
        return _match_section(_normalize_heading(stripped)) is not None
    if stripped.isupper() and 3 < len(stripped) < 80:
        return _match_section(_normalize_heading(stripped)) is not None
    return False


def _split_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = defaultdict(list)
    current: str | None = None
    for line in text.splitlines():
        if _is_section_heading(line):
            current = _match_section(_normalize_heading(line))
            continue
        if current is not None:
            sections[current].append(line)
    return sections


def _extract_title_company(text: str) -> tuple[str, str | None]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return "Untitled role", None

    title_line = lines[0]
    if _HEADING_RE.match(title_line):
        title_line = _HEADING_RE.match(title_line).group(1).strip()  # type: ignore[union-attr]

    company: str | None = None
    at_match = _AT_COMPANY_RE.search(title_line)
    if at_match:
        company = at_match.group(1).strip().rstrip("., ")
        title_line = _AT_COMPANY_RE.sub("", title_line).strip(" -–—|")

    title = title_line.strip() or "Untitled role"

    if company is None and len(lines) > 1:
        second = lines[1]
        if not _is_section_heading(second):
            label = _COMPANY_LABEL_RE.match(second)
            if label:
                company = label.group(1).strip()
            elif (
                len(second) < 80
                and not _BULLET_LIKE(second)
                and (
                    _COMPANY_SUFFIX_RE.search(second)
                    or (second[0].isupper() and " " not in second[:3])
                )
            ):
                company = second.strip()

    return title, company


def _BULLET_LIKE(line: str) -> bool:
    return bool(re.match(r"^[\s]*(?:[-*•]|\d+[.)])\s+", line))


def _parse_questions(
    sections: dict[str, list[str]],
    extra_questions: Sequence[str],
) -> list[Question]:
    raw: list[str] = []
    for key in SECTION_QUESTIONS:
        for line in sections.get(key, []):
            cleaned = line.strip()
            if not cleaned:
                continue
            cleaned = _QUESTION_PREFIX_RE.sub("", cleaned).strip()
            if cleaned:
                raw.append(cleaned)
    for q in extra_questions:
        q = q.strip()
        if q:
            raw.append(q)

    if not raw:
        raw = [DEFAULT_QUESTION]

    if len(raw) > MAX_QUESTIONS:
        raise JobParseError(f"at most {MAX_QUESTIONS} questions allowed")

    return [Question(id=f"Q{i + 1}", text=q[:500]) for i, q in enumerate(raw)]


def parse_job(
    text: str,
    lexicon: SkillLexicon,
    clock: Clock,
    extra_questions: Sequence[str] = (),
) -> JobPost:
    normalized = _normalize_job_text(text)
    if not normalized:
        raise JobParseError("job post is empty")
    if len(normalized) > MAX_JOB_CHARS:
        raise JobParseError(f"job post exceeds {MAX_JOB_CHARS} characters")

    warnings: list[str] = []
    sections = _split_sections(normalized)
    title, company = _extract_title_company(normalized)
    requirements = extract_requirements(sections, normalized, lexicon)

    if len(requirements) > MAX_REQUIREMENTS:
        warnings.append(f"only the first {MAX_REQUIREMENTS} requirements were kept")
        requirements = requirements[:MAX_REQUIREMENTS]

    questions = _parse_questions(sections, extra_questions)
    job_id = f"job-{hashlib.sha256(normalized.encode()).hexdigest()[:16]}"

    return JobPost(
        id=job_id,
        title=title,
        company=company,
        text=normalized,
        requirements=requirements,
        questions=questions,
        warnings=warnings,
        created_at=clock.now(),
    )
