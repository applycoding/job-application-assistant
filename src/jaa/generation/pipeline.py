"""Create and prune application runs."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from jaa.clock import Clock
from jaa.config import Settings
from jaa.export import is_stale
from jaa.generation.assemble import assemble_drafts
from jaa.ids import IdFactory
from jaa.models import Gap, RetrievalResult, Run, RunOptions
from jaa.privacy.outbound import build_outbound_draft
from jaa.providers.base import CallBudget, LLMProvider
from jaa.retrieval.service import retrieve_for_job
from jaa.storage.repo import Repository, RunData
from jaa.truth.deterministic import CHECK_RULES_VERSION, CheckContext
from jaa.truth.lexicon import SkillLexicon
from jaa.truth.prune import prune_flagged
from jaa.truth.report import run_truth_check

__all__ = ["Deps", "create_run", "prune_run", "is_stale", "RunDeadlineError"]


def _skill_gap_terms(gaps: list[Gap], lexicon: SkillLexicon) -> frozenset[str]:
    names = lexicon.skill_names
    return frozenset(g.term for g in gaps if g.term and g.term in names)


@dataclass
class Deps:
    repo: Repository
    provider: LLMProvider
    settings: Settings
    lexicon: SkillLexicon
    clock: Clock
    ids: IdFactory


class RunDeadlineError(TimeoutError):
    """Whole run exceeded deadline."""


async def create_run(deps: Deps, job_id: str, opts: RunOptions) -> Run:
    ref_date = deps.settings.resolved_reference_date(deps.clock.now().date())
    corpus_version, chunks = deps.repo.corpus_snapshot(ref_date)
    if not chunks:
        raise ValueError("upload documents first")

    job = deps.repo.get_job(job_id)
    result = retrieve_for_job(job, chunks, deps.lexicon)
    outbound = build_outbound_draft(job, result)
    pool = {item.chunk.id: item.chunk for item in result.evidence}
    judge_enabled = opts.judge if opts.judge is not None else deps.settings.judge
    model, judge_model = deps.settings.resolved_models()

    budget = CallBudget()
    if hasattr(deps.provider, "_budget"):
        deps.provider._budget = budget

    try:
        async with asyncio.timeout(deps.settings.run_deadline_s):
            draft_out = await deps.provider.draft(outbound)
    except TimeoutError as exc:
        raise RunDeadlineError(str(exc)) from exc

    drafts, warnings = assemble_drafts(draft_out, job, pool, deps.lexicon)
    req_map = {r.id: r for r in job.requirements}
    ctx = CheckContext(
        lexicon=deps.lexicon,
        reference_date=ref_date,
        target_company=job.company,
        gap_terms=_skill_gap_terms(result.gaps, deps.lexicon),
    )
    report = await run_truth_check(
        drafts,
        pool,
        ctx,
        deps.provider if judge_enabled else None,
        outbound,
        judge_enabled=judge_enabled,
        reqs=req_map,
    )

    data = RunData(
        job_id=job_id,
        parent_run_id=None,
        provider=deps.settings.provider,
        model=model,
        judge_model=judge_model if judge_enabled else None,
        judge_enabled=judge_enabled,
        corpus_version=corpus_version,
        check_rules_version=CHECK_RULES_VERSION,
        requirements=job.requirements,
        evidence=result.evidence,
        gaps=result.gaps,
        drafts=drafts,
        report=report,
        warnings=warnings,
    )
    return deps.repo.insert_run(data)


async def prune_run(deps: Deps, run_id: str) -> Run:
    parent = deps.repo.get_run(run_id)
    new_drafts, warnings = prune_flagged(parent.drafts, parent.report)
    ref_date = deps.settings.resolved_reference_date(deps.clock.now().date())
    corpus_version, _chunks = deps.repo.corpus_snapshot(ref_date)
    req_map = {r.id: r for r in parent.requirements}
    pool = {item.chunk.id: item.chunk for item in parent.evidence}
    job = deps.repo.get_job(parent.job_id)
    ctx = CheckContext(
        lexicon=deps.lexicon,
        reference_date=ref_date,
        target_company=job.company,
        gap_terms=_skill_gap_terms(parent.gaps, deps.lexicon),
    )
    outbound = build_outbound_draft(
        job,
        RetrievalResult(evidence=parent.evidence, gaps=parent.gaps),
    )
    report = await run_truth_check(
        new_drafts,
        pool,
        ctx,
        None,
        outbound,
        judge_enabled=False,
        reqs=req_map,
    )
    for sc in report.sentences:
        old = next((s for s in parent.report.sentences if s.sentence_id == sc.sentence_id), None)
        if old and old.judge:
            sc.judge = old.judge

    data = RunData(
        job_id=parent.job_id,
        parent_run_id=parent.id,
        provider=parent.provider,
        model=parent.model,
        judge_model=parent.judge_model,
        judge_enabled=parent.judge_enabled,
        corpus_version=parent.corpus_version,
        check_rules_version=parent.check_rules_version,
        requirements=parent.requirements,
        evidence=parent.evidence,
        gaps=parent.gaps,
        drafts=new_drafts,
        report=report,
        warnings=list(parent.warnings) + warnings,
    )
    return deps.repo.insert_run(data)
