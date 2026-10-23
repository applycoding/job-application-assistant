from datetime import date

from jaa.truth.dates import extract_spans, month_bounds


def test_present_span() -> None:
    spans = extract_spans("Mar 2021-present", date(2026, 10, 23))
    assert spans


def test_span_with_to_separator() -> None:
    ref = date(2026, 10, 23)
    spans = extract_spans("Mar 2019 to Oct 2026", ref)
    assert len(spans) == 1
    low, high = month_bounds(spans[0])
    assert low <= high
