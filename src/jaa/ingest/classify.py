"""Line classification and short-line filtering."""

from __future__ import annotations

import re

from jaa.ingest.normalize import normalize_line
from jaa.models import ChunkKind, RawLine
from jaa.truth.lexicon import SkillLexicon, count_tokens

_EMAIL_RE = re.compile(r"@[a-zA-Z0-9._%+-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}",
)
_URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
_LINKEDIN_RE = re.compile(r"linkedin\.com|github\.com", re.IGNORECASE)

_DOCX_HEADING_STYLES = frozenset({"Title", "Heading 1", "Heading 2", "Heading 3", "Heading 4"})


def classify(line: str, *, md_heading: bool, docx_style: str | None) -> ChunkKind:
    text = line.strip()
    if _is_contact_line(text):
        return "contact"
    if md_heading or (docx_style is not None and docx_style in _DOCX_HEADING_STYLES):
        return "heading"
    if text.startswith("|") and "|" in text[1:]:
        return "table_row"
    if re.match(r"^[\s]*(?:[-*•]|\d+[.)])\s+", line):
        return "bullet"
    return "line"


def _is_contact_line(text: str) -> bool:
    lowered = text.lower()
    if _EMAIL_RE.search(text):
        return True
    if _PHONE_RE.search(text):
        return True
    if _URL_RE.search(text) or _LINKEDIN_RE.search(lowered):
        return True
    if lowered.startswith("email:") or lowered.startswith("phone:") or lowered.startswith("tel:"):
        return True
    return False


def keep_line(line: RawLine, lexicon: SkillLexicon) -> bool:
    if line.kind in ("heading", "contact"):
        return True
    normalized = normalize_line(line.text)
    if not normalized:
        return False
    if lexicon.find(normalized):
        return True
    return count_tokens(normalized) >= 3
