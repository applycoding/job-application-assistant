from jaa.models import CheckFailure
from jaa.truth.verdict import status_from_checks


def test_fail_is_unsupported():
    f = [CheckFailure(check="number", token="1", detail="", outcome="fail")]
    assert status_from_checks(f, judge_enabled=False, judge=None) == "unsupported"


def test_abstain_is_not_verified():
    f = [CheckFailure(check="duration", token="6", detail="", outcome="abstain")]
    assert status_from_checks(f, judge_enabled=False, judge=None) == "not_verified"


def test_judge_false_makes_unsupported():
    from jaa.models import JudgeVerdict

    judge = JudgeVerdict(sentence_id="Q1.S1", entailed=False, rationale="no")
    assert status_from_checks([], judge_enabled=True, judge=judge) == "unsupported"
