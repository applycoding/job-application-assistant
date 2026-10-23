"""Text and filename normalization."""

from __future__ import annotations

import re
import unicodedata
from pathlib import PurePath

_BULLET_PREFIX = re.compile(
    r"^[\s]*(?:[-*•]+|\d+[.)])\s+",
)


def normalize_line(text: str) -> str:
    t = unicodedata.normalize("NFKC", text)
    t = re.sub(r"\s+", " ", t).strip()
    t = _BULLET_PREFIX.sub("", t)
    return t


def filename_key(filename: str) -> str:
    base = PurePath(filename).name
    return unicodedata.normalize("NFKC", base).casefold()
