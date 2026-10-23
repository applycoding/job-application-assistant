from datetime import date

from jaa.truth.dates import extract_spans


def test_present_span():
    spans = extract_spans("Mar 2021–present", date(2026, 10, 23))
    assert spans
