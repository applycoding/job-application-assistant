from __future__ import annotations

import re
from functools import lru_cache
from importlib import resources

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+#.]*", re.IGNORECASE)


@lru_cache(maxsize=1)
def _stopwords() -> frozenset[str]:
    raw = resources.files("jaa.resources").joinpath("stopwords.txt").read_text(encoding="utf-8")
    return frozenset(line.strip().lower() for line in raw.splitlines() if line.strip())


def tokenize(text: str) -> list[str]:
    lowered = text.lower()
    tokens: list[str] = []
    for match in _TOKEN_RE.finditer(lowered):
        tok = match.group(0)
        if tok.endswith("."):
            tok = tok[:-1]
        if not tok or tok in _stopwords():
            continue
        tokens.append(tok)
    return tokens
