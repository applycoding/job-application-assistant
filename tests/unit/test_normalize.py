"""Unit tests for ingest normalization."""

from jaa.ingest.normalize import filename_key, normalize_line


def test_normalize_strips_bullets_and_nfkc() -> None:
    assert normalize_line("  •  Hello   world  ") == "Hello world"
    assert normalize_line("1. Item") == "Item"


def test_filename_key_casefold() -> None:
    assert filename_key("path/CV.MD") == "cv.md"
