from __future__ import annotations

import re

_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
)
_PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)?\d{3}[\s.-]?\d{4}\b",
)
_URL_RE = re.compile(
    r"(?:https?://|www\.)[^\s<>\"']+",
    re.IGNORECASE,
)
_ADDRESS_RE = re.compile(
    r"\b\d{1,5}\s+[A-Za-z0-9'.-]+(?:\s+[A-Za-z0-9'.-]+){0,4}\s+"
    r"(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Way)\.?",
    re.IGNORECASE,
)
_INJECTION_RE = re.compile(
    r"(?i)ignore\s+previous[^\n]*|system:\s*override[^\n]*",
)


def redact(text: str) -> str:
    out = _EMAIL_RE.sub("[email]", text)
    out = _PHONE_RE.sub("[phone]", out)
    out = _URL_RE.sub("[url]", out)
    out = _ADDRESS_RE.sub("[address]", out)
    out = _INJECTION_RE.sub("[instruction]", out)
    return out
