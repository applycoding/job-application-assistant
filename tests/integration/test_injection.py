from pathlib import Path


def test_adversarial_fixture_readable() -> None:
    assert Path("tests/fixtures/adversarial/delimiter_escape.txt").read_text()
