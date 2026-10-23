from jaa.models import CheckFailure
from jaa.truth.verdict import status_from_checks


def test_fail_is_unsupported():
    f = [CheckFailure(check="number", token="1", detail="", outcome="fail")]
    assert status_from_checks(f, judge_enabled=False, judge=None) == "unsupported"
