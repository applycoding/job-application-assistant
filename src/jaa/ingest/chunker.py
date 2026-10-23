"""Stable chunk ids and corpus versioning."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from datetime import date

from jaa.ingest.loaders import IngestError
from jaa.limits import MAX_CHUNKS_PER_DOC, MAX_LINE_CHARS, RETRIEVAL_VERSION
from jaa.models import Chunk, RawLine
from jaa.truth.deterministic import CHECK_RULES_VERSION

_CHUNK_SEP = "\x1f"

_MONTH_SPAN_RE = re.compile(
    r"(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}"
    r"|\d{1,2}/\d{4}"
    r"|\d{4})"
    r"\s*[–—\-]\s*"
    r"(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}"
    r"|\d{1,2}/\d{4}"
    r"|\d{4}|present)",
    re.IGNORECASE,
)


class ChunkIdCollision(IngestError):
    """Hash prefix collision for distinct chunk content."""


def _section_str(path: list[str]) -> str:
    return " > ".join(path)


def _split_long_text(text: str) -> list[str]:
    if len(text) <= MAX_LINE_CHARS:
        return [text]
    parts: list[str] = []
    rest = text
    while len(rest) > MAX_LINE_CHARS:
        window = rest[: MAX_LINE_CHARS + 1]
        cut = window.rfind(". ")
        if cut < MAX_LINE_CHARS // 2:
            cut = window.rfind(" ")
        if cut < MAX_LINE_CHARS // 2:
            cut = MAX_LINE_CHARS
        parts.append(rest[:cut].strip())
        rest = rest[cut:].strip()
    if rest:
        parts.append(rest)
    return parts


def _expand_lines(lines: list[RawLine]) -> list[RawLine]:
    expanded: list[RawLine] = []
    for line in lines:
        for piece in _split_long_text(line.text):
            expanded.append(
                RawLine(
                    line_no=line.line_no,
                    text=piece,
                    kind=line.kind,
                    section=list(line.section),
                )
            )
    return expanded


def chunk_id(
    section: str,
    text: str,
    line_no: int,
    seen: dict[str, str],
    *,
    doc_scope: str,
) -> str:
    """Stable id from document content scope (file sha prefix) + line position + body."""
    content = f"{doc_scope}{_CHUNK_SEP}{line_no}{_CHUNK_SEP}{section}{_CHUNK_SEP}{text}"
    digest = hashlib.sha256(content.encode()).hexdigest()[:16]
    prior = seen.get(digest)
    if prior is not None and prior != content:
        raise ChunkIdCollision(f"Chunk id collision for digest {digest}")
    seen[digest] = content
    return digest


def chunk_document(
    doc_id: str,
    lines: list[RawLine],
    *,
    content_sha256: str | None = None,
) -> list[Chunk]:
    doc_scope = (content_sha256 or doc_id)[:16]
    expanded = _expand_lines(lines)
    if len(expanded) > MAX_CHUNKS_PER_DOC:
        raise IngestError(f"Document exceeds {MAX_CHUNKS_PER_DOC} chunks")
    digest_seen: dict[str, str] = {}
    occurrence: dict[str, int] = {}
    chunks: list[Chunk] = []
    for line in expanded:
        section = _section_str(line.section)
        text = line.text
        base = chunk_id(section, text, line.line_no, digest_seen, doc_scope=doc_scope)
        hex_part = base
        occurrence[hex_part] = occurrence.get(hex_part, 0) + 1
        n = occurrence[hex_part]
        cid = base if n == 1 else f"{base}~{n}"
        chunks.append(
            Chunk(
                id=cid,
                doc_id=doc_id,
                line_no=line.line_no,
                kind=line.kind,
                text=text,
                section=section,
            )
        )
    return chunks


def _date_spans(text: str) -> list[str]:
    return [m.group(0).lower() for m in _MONTH_SPAN_RE.finditer(text)]


def corpus_version(
    chunks: Iterable[Chunk],
    *,
    lexicon_version: str,
    reference_date: date,
) -> str:
    records: list[str] = []
    for chunk in sorted(chunks, key=lambda c: c.id):
        spans = _date_spans(chunk.section + "\n" + chunk.text)
        payload = {
            "id": chunk.id,
            "doc_id": chunk.doc_id,
            "kind": chunk.kind,
            "section": chunk.section,
            "text": chunk.text,
            "date_spans": spans,
        }
        records.append(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    tail = "|".join(
        [
            lexicon_version,
            RETRIEVAL_VERSION,
            CHECK_RULES_VERSION,
            reference_date.isoformat(),
        ]
    )
    body = "\n".join(records) + "\n" + tail
    return hashlib.sha256(body.encode()).hexdigest()
