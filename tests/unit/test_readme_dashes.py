"""README must not use Unicode en/em dashes (ASCII hyphen only)."""

from pathlib import Path

_DASH_CHARS = ("\u2013", "\u2014")  # en dash, em dash


def test_readme_has_no_unicode_dash_characters() -> None:
    text = Path("README.md").read_text(encoding="utf-8")
    for char in _DASH_CHARS:
        assert char not in text, f"README.md must not contain {char!r}"
