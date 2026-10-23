"""Assert PLAN prompt DATA-block boundaries in captured user messages."""

from __future__ import annotations

import re

_DATA_BLOCK_RE = re.compile(
    r"^BEGIN (DATA-[0-9a-f]{12})\n(?P<payload>.*)\nEND (DATA-[0-9a-f]{12})$",
    re.MULTILINE | re.DOTALL,
)


def split_user_message(user_message: str) -> tuple[str, str, str]:
    """Return (prefix_before_begin, payload_inside_block, suffix_after_end)."""
    lines = user_message.splitlines()
    try:
        begin_idx = next(i for i, line in enumerate(lines) if line.startswith("BEGIN DATA-"))
    except StopIteration:
        raise AssertionError("user message missing BEGIN DATA- block") from None
    tag = lines[begin_idx].removeprefix("BEGIN ").strip()
    end_marker = f"END {tag}"
    end_idx = next(i for i in range(begin_idx + 1, len(lines)) if lines[i] == end_marker)
    prefix = "\n".join(lines[:begin_idx])
    payload = "\n".join(lines[begin_idx + 1 : end_idx])
    suffix = "\n".join(lines[end_idx + 1 :])
    return prefix, payload, suffix


def assert_text_only_inside_data_block(user_message: str, needle: str) -> None:
    prefix, payload, suffix = split_user_message(user_message)
    assert needle in payload, f"{needle!r} missing from DATA payload"
    assert needle not in prefix, f"{needle!r} leaked before DATA block"
    assert needle not in suffix, f"{needle!r} leaked after DATA block"


def assert_data_block_well_formed(user_message: str) -> None:
    body = user_message.strip()
    m = _DATA_BLOCK_RE.search(body)
    assert m is not None, "user message missing BEGIN/END DATA block"
    begin_tag = body.splitlines()[next(i for i, l in enumerate(body.splitlines()) if l.startswith("BEGIN DATA-"))]
    end_tag = body.splitlines()[next(i for i, l in enumerate(body.splitlines()) if l.startswith("END DATA-"))]
    assert begin_tag.replace("BEGIN ", "") == end_tag.replace("END ", "")
