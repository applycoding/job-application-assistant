#!/usr/bin/env python3
"""Write ``samples/alex-doe-certificates.pdf`` with stable bytes."""

from __future__ import annotations

from pathlib import Path

# Hand-built PDF 1.4 with fixed object offsets (no timestamps).
_PDF = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]
   /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 260 >>
stream
BT
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
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000266 00000 n 
0000000578 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
655
%%EOF
"""

OUT = Path(__file__).resolve().parent.parent / "samples" / "alex-doe-certificates.pdf"


def main() -> None:
    OUT.write_bytes(_PDF)


if __name__ == "__main__":
    main()
