"""Tutorial code excerpts must match repository source."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_tutorial_06_redact_lines_match_outbound_source() -> None:
    tutorial = (ROOT / "docs/tutorial/06-providers-and-the-mock.md").read_text(encoding="utf-8")
    source = (ROOT / "src/jaa/privacy/outbound.py").read_text(encoding="utf-8")
    for line in (
        "section=redact(item.chunk.section),",
        "text=redact(item.chunk.text),",
    ):
        assert line in tutorial
        assert line in source
