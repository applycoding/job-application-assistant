#!/usr/bin/env python3
"""Write ``samples/alex-doe-certificates.pdf`` with stable bytes."""

from __future__ import annotations

import io
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject

OUT = Path(__file__).resolve().parent.parent / "samples" / "alex-doe-certificates.pdf"

_CONTENT = b"""BT
/F1 11 Tf
72 720 Td
(FICTIONAL SAMPLE DATA - Alex Doe is not a real person.) Tj
0 -18 Td
(Alex Doe - Certificates) Tj
0 -18 Td
(Example Cloud Practitioner - Example Institute 2022) Tj
0 -18 Td
(Data Engineering Specialty - Example Board 2023) Tj
ET
"""


def _build_pdf_bytes() -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_ref = writer._add_object(font)
    resources = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})}
    )
    stream = DecodedStreamObject()
    stream.set_data(_CONTENT)
    stream[NameObject("/Length")] = NumberObject(len(_CONTENT))
    page[NameObject("/Resources")] = resources
    page[NameObject("/Contents")] = writer._add_object(stream)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


_PDF = _build_pdf_bytes()


def main() -> None:
    OUT.write_bytes(_PDF)


if __name__ == "__main__":
    main()
