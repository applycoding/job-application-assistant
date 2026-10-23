"""Optional LLM judge for claims that passed deterministic checks."""

from __future__ import annotations

from collections.abc import Sequence

from jaa.models import Sentence, SentenceCheck
from jaa.privacy.outbound import OutboundDraft, build_outbound_judge
from jaa.providers.base import JudgeUnavailable, LLMProvider
from jaa.truth.verdict import status_from_checks


async def apply_judge(
    checks: list[SentenceCheck],
    claims: Sequence[Sentence],
    provider: LLMProvider,
    outbound: OutboundDraft,
) -> list[SentenceCheck]:
    eligible = [
        c
        for c in checks
        if c.status == "checks_passed" and not c.failures
    ]
    if not eligible:
        return checks

    claim_by_id = {c.id: c for c in claims}
    to_judge = [claim_by_id[c.sentence_id] for c in eligible if c.sentence_id in claim_by_id]
    judge_req = build_outbound_judge(to_judge, outbound)

    try:
        judge_out = await provider.judge(judge_req)
    except JudgeUnavailable:
        return [
            _mark_judge_unavailable(c) if c.sentence_id in {x.sentence_id for x in eligible} else c
            for c in checks
        ]

    verdict_map = {v.sentence_id: v for v in judge_out.verdicts}
    updated: list[SentenceCheck] = []
    for check in checks:
        if check.sentence_id not in verdict_map:
            updated.append(check)
            continue
        verdict = verdict_map[check.sentence_id]
        failures = list(check.failures)
        if not verdict.entailed:
            from jaa.models import CheckFailure

            failures.append(
                CheckFailure(
                    check="judge",
                    token=None,
                    detail=verdict.rationale,
                    outcome="fail",
                )
            )
        status = status_from_checks(failures, judge_enabled=True, judge=verdict)
        updated.append(
            SentenceCheck(
                sentence_id=check.sentence_id,
                status=status,
                failures=failures,
                checks_run=check.checks_run + (["judge"] if not verdict.entailed else []),
                judge=verdict,
            )
        )
    return updated


def _mark_judge_unavailable(check: SentenceCheck) -> SentenceCheck:
    from jaa.models import CheckFailure

    failures = list(check.failures)
    failures.append(
        CheckFailure(
            check="judge",
            token=None,
            detail="Judge unavailable",
            outcome="abstain",
        )
    )
    status = status_from_checks(failures, judge_enabled=True, judge=None)
    return SentenceCheck(
        sentence_id=check.sentence_id,
        status=status,
        failures=failures,
        checks_run=check.checks_run + ["judge"],
        judge=None,
    )
