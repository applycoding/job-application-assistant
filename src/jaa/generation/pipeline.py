"""Create and prune application runs."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from jaa.clock import Clock
from jaa.config import Settings
from jaa.generation.assemble import assemble_drafts
from jaa.ids import IdFactory
from jaa.models import RetrievalResult, Run, RunOptions
from jaa.privacy.outbound import build_outbound_draft
from jaa.providers.base import CallBudget, ProviderError
from jaa.providers.base import LLMProvider
from jaa.retrieval.service import retrieve_for_job
from jaa.storage.repo import Repository, RunData
from jaa.truth.deterministic import CHECK_RULES_VERSION, CheckContext
from jaa.truth.lexicon import SkillLexicon
from jaa.export import is_stale
from jaa.truth.prune import prune_flagged
from jaa.truth.report import run_truth_check

__all__ = ["Deps", "create_run", "prune_run", "is_stale", "RunDeadlineError"]


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
        raise ProviderError("Upload documents first")

    job = deps.repo.get_job(job_id)
    result = retrieve_for_job(job, chunks, deps.lexicon)
    outbound = build_outbound_draft(job, result)
    pool = {item.chunk.id: item.chunk for item in result.evidence}
    judge_enabled = opts.judge if opts.judge is not None else deps.settings.judge
    model, judge_model = deps.settings.resolved_models()

    budget = CallBudget()
    if hasattr(deps.provider, "_budget"):
        deps.provider._budget = budget  # type: ignore[attr-defined]

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

    run_payload = {
        "job_id": job_id,
        "parent_run_id": None,
        "created_at": deps.clock.now(),
        "provider": deps.settings.provider,
        "model": model,
        "judge_model": judge_model if judge_enabled else None,
        "judge_enabled": judge_enabled,
        "corpus_version": corpus_version,
        "check_rules_version": CHECK_RULES_VERSION,
        "requirements": job.requirements,
        "evidence": result.evidence,
        "gaps": result.gaps,
        "drafts": drafts,
        "report": report,
        "warnings": warnings,
    }
    data = RunData(
        job_id=job_id,
        parent_run_id=None,
        provider=deps.settings.provider,
        model=model,
        judge_model=judge_model if judge_enabled else None,
        judge_enabled=judge_enabled,
        corpus_version=corpus_version,
        check_rules_version=CHECK_RULES_VERSION,
        payload=run_payload,
    )
    return deps.repo.insert_run(data)


async def prune_run(deps: Deps, run_id: str) -> Run:
    parent = deps.repo.get_run(run_id)
    new_drafts, warnings = prune_flagged(parent.drafts, parent.report)
    ref_date = deps.settings.resolved_reference_date(deps.clock.now().date())
    corpus_version, _chunks = deps.repo.corpus_snapshot(ref_date)
    req_map = {r.id: r for r in parent.requirements}
    pool = {item.chunk.id: item.chunk for item in parent.evidence}
    ctx = CheckContext(
        lexicon=deps.lexicon,
        reference_date=ref_date,
        target_company=None,
    )
    job = deps.repo.get_job(parent.job_id)
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

    payload = parent.model_dump()
    payload.update(
        {
            "parent_run_id": parent.id,
            "created_at": deps.clock.now(),
            "drafts": new_drafts,
            "report": report,
            "warnings": list(parent.warnings) + warnings,
            "corpus_version": parent.corpus_version,
        }
    )
    data = RunData(
        job_id=parent.job_id,
        parent_run_id=parent.id,
        provider=parent.provider,
        model=parent.model,
        judge_model=parent.judge_model,
        judge_enabled=parent.judge_enabled,
        corpus_version=parent.corpus_version,
        check_rules_version=parent.check_rules_version,
        payload=payload,
    )
    return deps.repo.insert_run(data)
