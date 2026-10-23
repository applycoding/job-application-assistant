#!/usr/bin/env python3
"""Write ``samples/alex-doe-certificates.pdf`` with stable, valid PDF bytes."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject

OUT = Path(__file__).resolve().parent.parent / "samples" / "alex-doe-certificates.pdf"

_CONTENT = b"""BT
/F1 11 Tf
72 720 Td
(FICTIONAL SAMPLE DATA for portfolio demo only.) Tj
0 -18 Td
(Alex Doe - Certificates) Tj
0 -18 Td
(Example Cloud Practitioner - Example Institute 2022) Tj
0 -18 Td
(Data Engineering Specialty - Example Board 2023) Tj
ET
"""


def main() -> None:
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
    resources = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})})
    stream = DecodedStreamObject()
    stream.set_data(_CONTENT)
    stream[NameObject("/Length")] = NumberObject(len(_CONTENT))
    page[NameObject("/Resources")] = resources
    page[NameObject("/Contents")] = writer._add_object(stream)
    with OUT.open("wb") as fh:
        writer.write(fh)


if __name__ == "__main__":
    main()
