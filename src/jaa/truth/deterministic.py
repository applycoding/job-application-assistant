"""Deterministic truth checks per claim."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from jaa.models import CheckFailure, CheckName, Chunk, Sentence, SentenceCheck
from jaa.truth.dates import extract_spans, month_bounds
from jaa.truth.extractors import (
    DurationMention,
    extract_durations,
    extract_numbers,
    extract_orgs,
    extract_ownership,
    extract_skill_versions,
    extract_years,
    negated_terms,
    number_in_text,
)
from jaa.truth.lexicon import SkillLexicon
from jaa.truth.verdict import status_from_checks

CHECK_RULES_VERSION = "2026-10-23.1"


@dataclass(frozen=True)
class CheckContext:
    lexicon: SkillLexicon
    reference_date: date
    target_company: str | None


def check_sentence(
    s: Sentence,
    pool: Mapping[str, Chunk],
    ctx: CheckContext,
) -> SentenceCheck:
    if s.kind == "framing":
        return SentenceCheck(
            sentence_id=s.id,
            status="checks_passed",
            failures=[],
            checks_run=[],
            judge=None,
        )

    failures: list[CheckFailure] = []
    checks_run: list[CheckName] = []

    if not s.citations:
        failures.append(
            CheckFailure(check="no_citation", token=None, detail="No citations", outcome="fail")
        )
        return SentenceCheck(
            sentence_id=s.id,
            status="unsupported",
            failures=failures,
            checks_run=["no_citation"],
            judge=None,
        )

    cited = [pool[cid] for cid in s.citations if cid in pool]
    for cid in s.citations:
        if cid not in pool:
            failures.append(
                CheckFailure(
                    check="invalid_citation",
                    token=cid,
                    detail=f"Unknown chunk id {cid}",
                    outcome="fail",
                )
            )
    if failures:
        return SentenceCheck(
            sentence_id=s.id,
            status="unsupported",
            failures=failures,
            checks_run=["invalid_citation"],
            judge=None,
        )

    claim_text = s.text
    durations = extract_durations(claim_text)
    duration_nums = {d.years for d in durations}

    numbers = [
        n
        for n in extract_numbers(claim_text)
        if not any(d.years == n.value for d in durations if isinstance(n.value, int))
    ]
    years = extract_years(claim_text)
    orgs = extract_orgs(claim_text, ctx.lexicon)
    ownership = extract_ownership(claim_text)
    skills_in_claim = ctx.lexicon.find(claim_text)
    skill_versions = extract_skill_versions(claim_text, ctx.lexicon)

    supporting = _find_supporting_chunk(
        cited,
        numbers=numbers,
        years=years,
        orgs=orgs,
        ownership=ownership,
        ctx=ctx,
    )

    if supporting is None and cited:
        if _facts_split_across_chunks(cited, numbers, years, orgs, ownership, ctx):
            failures.append(
                CheckFailure(
                    check="mixed_citations",
                    token=None,
                    detail="Facts split across citations",
                    outcome="fail",
                )
            )
            checks_run.append("mixed_citations")
        else:
            for n in numbers:
                if not _number_in_any(n, cited):
                    failures.append(
                        CheckFailure(
                            check="number",
                            token=str(int(n.value)) if n.value == int(n.value) else str(n.value),
                            detail=f"Number {n.raw} not in evidence",
                            outcome="fail",
                        )
                    )
            for y in years:
                if not _year_in_any(y, cited):
                    failures.append(
                        CheckFailure(
                            check="year",
                            token=str(y),
                            detail=f"Year {y} not in evidence",
                            outcome="fail",
                        )
                    )
            for org in orgs:
                if not _org_in_any(org, cited):
                    failures.append(
                        CheckFailure(
                            check="employer",
                            token=org,
                            detail=f"Employer {org} not in evidence",
                            outcome="fail",
                        )
                    )
            for lemma in ownership:
                if not _ownership_in_any(lemma, cited):
                    failures.append(
                        CheckFailure(
                            check="ownership",
                            token=lemma,
                            detail=f"Ownership {lemma} not in evidence",
                            outcome="fail",
                        )
                    )

    if supporting is not None:
        ev = supporting.evidence_text
        for n in numbers:
            if not number_in_text(n.value, ev) and not _number_in_text_loose(n, ev):
                failures.append(
                    CheckFailure(
                        check="number",
                        token=str(int(n.value)),
                        detail=f"Number {n.raw} not in supporting chunk",
                        outcome="fail",
                    )
                )
        for y in years:
            if not _year_in_text(y, ev):
                failures.append(
                    CheckFailure(
                        check="year",
                        token=str(y),
                        detail=f"Year {y} not in supporting chunk",
                        outcome="fail",
                    )
                )
        for org in orgs:
            if org.lower() not in ev.lower():
                failures.append(
                    CheckFailure(
                        check="employer",
                        token=org,
                        detail=f"Employer {org} not in supporting chunk",
                        outcome="fail",
                    )
                )
        for lemma in ownership:
            if lemma not in extract_ownership(ev):
                failures.append(
                    CheckFailure(
                        check="ownership",
                        token=lemma,
                        detail=f"Ownership {lemma} not active in supporting chunk",
                        outcome="fail",
                    )
                )

        terms = set(ctx.lexicon.find(claim_text)) | set(s.requirement_ids)
        for term in terms:
            claim_neg = term in negated_terms(claim_text, [term])
            chunk_neg = term in negated_terms(ev, [term])
            if term.lower() in ev.lower() and claim_neg != chunk_neg:
                failures.append(
                    CheckFailure(
                        check="negation",
                        token=term,
                        detail="Negation mismatch",
                        outcome="fail",
                    )
                )

    for skill in skills_in_claim:
        if not any(skill.lower() in c.evidence_text.lower() for c in cited):
            failures.append(
                CheckFailure(
                    check="skill",
                    token=skill,
                    detail=f"Skill {skill} not in citations",
                    outcome="fail",
                )
            )

    for skill, ver in skill_versions:
        if not _skill_version_in_citations(skill, ver, cited, ctx.lexicon):
            failures.append(
                CheckFailure(
                    check="skill_version",
                    token=f"{skill}:{ver}",
                    detail="Skill version mismatch",
                    outcome="fail",
                )
            )

    if ctx.target_company and ctx.target_company.lower() in claim_text.lower():
        if not any(ctx.target_company.lower() in c.evidence_text.lower() for c in cited):
            failures.append(
                CheckFailure(
                    check="employer",
                    token=ctx.target_company,
                    detail="Target company not in evidence",
                    outcome="fail",
                )
            )

    dur_failure = _check_duration(claim_text, cited, skills_in_claim, ctx, durations)
    if dur_failure is not None:
        failures.append(dur_failure)

    checks_run.extend(sorted({f.check for f in failures}))
    status = status_from_checks(failures, judge_enabled=False, judge=None)
    return SentenceCheck(
        sentence_id=s.id,
        status=status,
        failures=failures,
        checks_run=checks_run,
        judge=None,
    )


def _find_supporting_chunk(
    cited: list[Chunk],
    *,
    numbers,
    years: list[int],
    orgs: list[str],
    ownership: set[str],
    ctx: CheckContext,
) -> Chunk | None:
    for chunk in cited:
        ev = chunk.evidence_text
        ok = True
        for n in numbers:
            if not number_in_text(n.value, ev) and not _number_in_text_loose(n, ev):
                ok = False
        for y in years:
            if not _year_in_text(y, ev):
                ok = False
        for org in orgs:
            if org.lower() not in ev.lower():
                ok = False
        for lemma in ownership:
            if lemma not in extract_ownership(ev):
                ok = False
        if ok:
            return chunk
    return None


def _facts_split_across_chunks(
    cited: list[Chunk],
    numbers,
    years: list[int],
    orgs: list[str],
    ownership: set[str],
    ctx: CheckContext,
) -> bool:
    if not (numbers or years or orgs or ownership):
        return False
    if _find_supporting_chunk(cited, numbers=numbers, years=years, orgs=orgs, ownership=ownership, ctx=ctx):
        return False
    any_fact = False
    all_in_some = True
    for n in numbers:
        any_fact = True
        if not _number_in_any(n, cited):
            all_in_some = False
    for y in years:
        any_fact = True
        if not _year_in_any(y, cited):
            all_in_some = False
    for org in orgs:
        any_fact = True
        if not _org_in_any(org, cited):
            all_in_some = False
    for lemma in ownership:
        any_fact = True
        if not _ownership_in_any(lemma, cited):
            all_in_some = False
    return any_fact and all_in_some


def _number_in_any(n, cited: list[Chunk]) -> bool:
    return any(number_in_text(n.value, c.evidence_text) for c in cited)


def _number_in_text_loose(n, text: str) -> bool:
    return str(int(n.value)) in text.replace(",", "")


def _year_in_any(y: int, cited: list[Chunk]) -> bool:
    return any(_year_in_text(y, c.evidence_text) for c in cited)


def _year_in_text(y: int, text: str) -> bool:
    if str(y) in text:
        return True
    for span in extract_spans(text, date.today()):
        if y in (span.start_year, span.end_year):
            return True
    return False


def _org_in_any(org: str, cited: list[Chunk]) -> bool:
    return any(org.lower() in c.evidence_text.lower() for c in cited)


def _ownership_in_any(lemma: str, cited: list[Chunk]) -> bool:
    return any(lemma in extract_ownership(c.evidence_text) for c in cited)


def _skill_version_in_citations(
    skill: str,
    version: str,
    cited: list[Chunk],
    lexicon: SkillLexicon,
) -> bool:
    for chunk in cited:
        pairs = extract_skill_versions(chunk.evidence_text, lexicon)
        for sk, ver in pairs:
            if sk.lower() == skill.lower() and ver == version:
                return True
        if re.search(
            rf"\b{re.escape(skill)}[^\d]*{re.escape(version)}\b",
            chunk.evidence_text,
            re.IGNORECASE,
        ):
            return True
    return False


def _check_duration(
    claim_text: str,
    cited: list[Chunk],
    skills: set[str],
    ctx: CheckContext,
    durations: list[DurationMention],
) -> CheckFailure | None:
    if not durations:
        return None
    dur = durations[0]
    required_months = dur.years * 12
    if dur.strict_more:
        required_months += 1
    elif dur.plus:
        required_months = dur.years * 12

    for chunk in cited:
        ev = chunk.evidence_text
        if skills and not any(s.lower() in ev.lower() for s in skills):
            continue
        spans = extract_spans(ev, ctx.reference_date)
        if spans:
            low, high = month_bounds(spans[0])
            if low >= required_months:
                return None
            if high < required_months:
                return CheckFailure(
                    check="duration",
                    token=str(dur.years),
                    detail="Duration not met",
                    outcome="fail",
                )
            return CheckFailure(
                check="duration",
                token=str(dur.years),
                detail="Ambiguous duration",
                outcome="abstain",
            )
        ev_durations = extract_durations(ev)
        for ed in ev_durations:
            months = ed.years * 12
            if ed.strict_more and months > required_months:
                return None
            if not ed.strict_more and months >= required_months:
                return None
    return CheckFailure(
        check="duration",
        token=str(dur.years),
        detail="No duration evidence",
        outcome="abstain",
    )
