"""Date span parsing for duration checks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

_SPAN_RE = re.compile(
    r"(?P<s_m>\d{1,2}/\d{4}|[A-Za-z]{3,9}\s+\d{4}|\d{4})"
    r"\s*(?:[\u2013\u2014\-–—]|to)\s*"
    r"(?P<e_m>\d{1,2}/\d{4}|[A-Za-z]{3,9}\s+\d{4}|\d{4}|present)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class MonthSpan:
    start_year: int
    end_year: int
    start_month: int | None
    end_month: int | None
    raw: str


def extract_spans(text: str, reference: date) -> list[MonthSpan]:
    spans: list[MonthSpan] = []
    for m in _SPAN_RE.finditer(text):
        start = _parse_endpoint(m.group("s_m"))
        end_raw = m.group("e_m")
        if end_raw.lower() == "present":
            end_year = reference.year
            end_month: int | None = reference.month
        else:
            end_parsed = _parse_endpoint(end_raw)
            end_year = end_parsed[0]
            end_month = end_parsed[1]
        spans.append(
            MonthSpan(
                start_year=start[0],
                end_year=end_year,
                start_month=start[1],
                end_month=end_month,
                raw=m.group(0),
            )
        )
    return spans


def _parse_endpoint(part: str) -> tuple[int, int | None]:
    part = part.strip()
    if "/" in part:
        mo_s, yr_s = part.split("/", 1)
        return int(yr_s), int(mo_s)
    pieces = part.split()
    if len(pieces) == 2:
        mo = _MONTHS.get(pieces[0].lower(), 1)
        return int(pieces[1]), mo
    return int(part), None


def month_bounds(span: MonthSpan) -> tuple[int, int]:
    start_m = span.start_month or 1
    end_m = span.end_month or 12
    start_total = span.start_year * 12 + (start_m - 1)
    end_total = span.end_year * 12 + (end_m - 1)
    months = max(0, end_total - start_total + 1)
    if span.start_month is None or span.end_month is None:
        return months, months + 11
    return months, months
