"""Map check failures to claim status."""

from __future__ import annotations

from jaa.models import CheckFailure, ClaimStatus, JudgeVerdict


def status_from_checks(
    failures: list[CheckFailure],
    *,
    judge_enabled: bool,
    judge: JudgeVerdict | None,
) -> ClaimStatus:
    if any(f.outcome == "fail" for f in failures):
        return "unsupported"
    if any(f.outcome == "abstain" for f in failures):
        return "not_verified"
    if judge_enabled:
        if judge is None:
            return "not_verified"
        if not judge.entailed:
            return "unsupported"
        return "entailed"
    return "checks_passed"
