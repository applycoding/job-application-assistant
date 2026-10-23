"""Load bytes into classified ``RawLine`` lists."""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

from docx import Document as DocxDocument
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
from fastapi import UploadFile
from pypdf import PdfReader

from jaa.ingest.classify import classify
from jaa.ingest.normalize import normalize_line
from jaa.limits import (
    DOCX_MAX_DECOMPRESSED_BYTES,
    DOCX_MAX_ZIP_ENTRIES,
    MAX_EXTRACTED_CHARS,
    PDF_MAX_PAGES,
)
from jaa.models import ChunkKind, MediaType, RawLine

_MD_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


class IngestError(ValueError):
    """Client error during ingest (422)."""


class UploadTooLarge(IngestError):
    """Upload exceeds size limit (413)."""


async def read_upload_limited(f: UploadFile, max_bytes: int) -> bytes:
    buf = bytearray()
    limit = max_bytes + 1
    while len(buf) < limit:
        chunk = await f.read(64 * 1024)
        if not chunk:
            break
        buf.extend(chunk)
    if len(buf) > max_bytes:
        raise UploadTooLarge(f"Upload exceeds {max_bytes} bytes")
    return bytes(buf)


def detect_media_type(filename: str, head: bytes) -> MediaType:
    ext = Path(filename).suffix.lower()
    ext_map = {".md": "md", ".txt": "txt", ".pdf": "pdf", ".docx": "docx"}
    if ext not in ext_map:
        raise IngestError(f"Unsupported file extension: {ext or '(none)'}")
    media = ext_map[ext]
    if media == "pdf" and not head.startswith(b"%PDF"):
        raise IngestError("File extension is .pdf but content is not a PDF")
    if media == "docx" and not head.startswith(b"PK"):
        raise IngestError("File extension is .docx but content is not a ZIP archive")
    return media


def decode_text(data: bytes) -> str:
    if b"\x00" in data:
        raise IngestError("not UTF-8 text")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise IngestError("not UTF-8 text") from None


def load_lines(
    data: bytes,
    media_type: MediaType,
) -> tuple[list[RawLine], list[str]]:
    warnings: list[str] = []
    if media_type in ("md", "txt"):
        text = decode_text(data)
        if len(text) > MAX_EXTRACTED_CHARS:
            raise IngestError(f"Extracted text exceeds {MAX_EXTRACTED_CHARS} characters")
        return _load_text_lines(text, media_type == "md"), warnings
    if media_type == "pdf":
        return _load_pdf(data, warnings)
    if media_type == "docx":
        return _load_docx(data, warnings)
    raise IngestError(f"Unsupported media type: {media_type}")


def _load_text_lines(text: str, is_md: bool) -> list[RawLine]:
    lines_out: list[RawLine] = []
    section: list[str] = []
    for line_no, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip() and not raw:
            continue
        md_heading = False
        content = raw
        if is_md:
            m = _MD_HEADING.match(raw.strip())
            if m:
                md_heading = True
                content = m.group(2).strip()
                section = [content]
        normalized = normalize_line(content) if not md_heading else content.strip()
        if not normalized and not md_heading:
            continue
        kind = classify(raw, md_heading=md_heading, docx_style=None)
        if kind == "heading" and not is_md:
            section = [normalized]
        lines_out.append(
            RawLine(
                line_no=line_no,
                text=normalized if kind != "heading" else content.strip(),
                kind=kind,
                section=list(section),
            )
        )
    return lines_out


def _load_pdf(data: bytes, warnings: list[str]) -> tuple[list[RawLine], list[str]]:
    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        raise IngestError("PDF is encrypted")
    if len(reader.pages) > PDF_MAX_PAGES:
        raise IngestError(f"PDF exceeds {PDF_MAX_PAGES} pages")
    parts: list[str] = []
    for page in reader.pages:
        extracted = page.extract_text() or ""
        parts.append(extracted)
    text = "\n".join(parts)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    if len(text) > MAX_EXTRACTED_CHARS:
        raise IngestError(f"Extracted text exceeds {MAX_EXTRACTED_CHARS} characters")
    if not text.strip():
        raise IngestError("PDF contains no extractable text")
    return _load_text_lines(text, is_md=False), warnings


def _load_docx(data: bytes, warnings: list[str]) -> tuple[list[RawLine], list[str]]:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise IngestError("Invalid DOCX archive") from None
    names = zf.namelist()
    if len(names) > DOCX_MAX_ZIP_ENTRIES:
        raise IngestError(f"DOCX exceeds {DOCX_MAX_ZIP_ENTRIES} zip entries")
    total = 0
    for info in zf.infolist():
        total += info.file_size
        if total > DOCX_MAX_DECOMPRESSED_BYTES:
            raise IngestError("DOCX declared decompressed size exceeds limit")
    if "word/document.xml" not in names:
        raise IngestError("DOCX missing word/document.xml")

    read_total = 0
    for name in names:
        with zf.open(name) as entry:
            chunk = entry.read(1024 * 1024)
            read_total += len(chunk)
            while chunk:
                extra = entry.read(1024 * 1024)
                read_total += len(extra)
                chunk = extra
                if read_total > DOCX_MAX_DECOMPRESSED_BYTES:
                    raise IngestError("DOCX decompressed size exceeds limit")

    doc = DocxDocument(io.BytesIO(data))
    lines_out: list[RawLine] = []
    section: list[str] = []
    line_no = 0
    body = doc.element.body
    for child in body:
        if child.tag == qn("w:p"):
            para = Paragraph(child, doc)
            text = para.text.strip()
            if not text:
                continue
            line_no += 1
            style_name = para.style.name if para.style is not None else None
            kind = classify(text, md_heading=False, docx_style=style_name)
            if kind == "heading":
                section = [text]
            lines_out.append(
                RawLine(
                    line_no=line_no,
                    text=text,
                    kind=kind,
                    section=list(section),
                )
            )
        elif child.tag == qn("w:tbl"):
            table = Table(child, doc)
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells]
                row_text = " | ".join(cells)
                if not row_text.strip():
                    continue
                line_no += 1
                lines_out.append(
                    RawLine(
                        line_no=line_no,
                        text=row_text,
                        kind="table_row",
                        section=list(section),
                    )
                )
    if not lines_out:
        raise IngestError("DOCX contains no text")
    full = "\n".join(ln.text for ln in lines_out)
    if len(full) > MAX_EXTRACTED_CHARS:
        raise IngestError(f"Extracted text exceeds {MAX_EXTRACTED_CHARS} characters")
    return lines_out, warnings
