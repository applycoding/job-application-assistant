"""Normalize runs for golden JSON comparison."""

from __future__ import annotations

import json
from typing import Any

from jaa.models import Run


def _round_floats(obj: object) -> object:
    if isinstance(obj, float):
        return round(obj, 6)
    if isinstance(obj, dict):
        return {k: _round_floats(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [_round_floats(v) for v in obj]
    return obj


def run_to_golden_dict(
    run: Run, *, fixed_time: str = "2026-10-23T09:00:00+00:00"
) -> dict[str, Any]:
    data = run.model_dump(mode="json")
    data["id"] = run.id
    data["created_at"] = fixed_time
    return _round_floats(data)  # type: ignore[return-value]


def dump_golden(run: Run) -> str:
    return json.dumps(run_to_golden_dict(run), indent=2, sort_keys=True, ensure_ascii=True)


def load_golden(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def assert_golden_run(run: Run, path: str, *, update: bool = False) -> None:
    from pathlib import Path

    p = Path(path)
    expected = load_golden(str(p)) if p.is_file() else None
    actual = run_to_golden_dict(run)
    if update or expected is None:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(actual, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8"
        )
        return
    assert actual == expected
