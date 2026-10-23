"""Verify tutorial chapters front matter and checkpoints."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

TUTORIAL = Path("docs/tutorial")
CHAPTER_RE = re.compile(r"^(\d{2})-.*\.md$")


def _parse_front_matter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    block = text[3:end]
    data: dict[str, str] = {}
    for line in block.splitlines():
        if ":" in line:
            key, val = line.split(":", 1)
            data[key.strip()] = val.strip()
    return data


@pytest.mark.parametrize("n", range(13))
def test_chapter_exists(n: int) -> None:
    matches = list(TUTORIAL.glob(f"{n:02d}-*.md"))
    assert len(matches) == 1, f"missing chapter {n:02d}"


def test_chapter_modules_exist() -> None:
    for path in sorted(TUTORIAL.glob("*.md")):
        fm = _parse_front_matter(path.read_text(encoding="utf-8"))
        modules = fm.get("modules", "")
        for part in modules.split():
            if part.endswith(".py") or "/" in part:
                p = Path(part)
                if p.suffix == ".py":
                    assert p.is_file(), f"{path.name}: missing {part}"


def test_checkpoints_collect() -> None:
    for path in sorted(TUTORIAL.glob("*.md")):
        fm = _parse_front_matter(path.read_text(encoding="utf-8"))
        checkpoint = fm.get("checkpoint", "")
        if not checkpoint:
            continue
        if checkpoint.startswith("uv run jaa"):
            continue
        cmd = checkpoint.replace("uv run ", ".venv/bin/", 1)
        proc = subprocess.run(
            cmd.split() + ["--collect-only", "-q"],
            cwd=Path("."),
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stderr
        assert "test session starts" in proc.stdout.lower() or "test" in proc.stdout
