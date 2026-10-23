"""Run-level truth checking."""

from __future__ import annotations

from collections.abc import Mapping

from jaa.generation.explain import explain
from jaa.models import Chunk, Drafts, Requirement, Sentence, TruthReport
from jaa.privacy.outbound import OutboundDraft
from jaa.providers.base import LLMProvider
from jaa.truth.deterministic import CheckContext, check_sentence
from jaa.truth.judge import apply_judge


def iter_claim_sentences(drafts: Drafts) -> list[Sentence]:
    claims: list[Sentence] = []
    for ans in drafts.answers:
        claims.extend(s for s in ans.sentences if s.kind == "claim")
    claims.extend(s for s in drafts.cover_note.sentences if s.kind == "claim")
    return claims


async def run_truth_check(
    drafts: Drafts,
    pool: Mapping[str, Chunk],
    ctx: CheckContext,
    judge: LLMProvider | None,
    outbound: OutboundDraft,
    *,
    judge_enabled: bool,
    reqs: Mapping[str, Requirement],
) -> TruthReport:
    from jaa.truth.lexicon import SkillLexicon

    lexicon = ctx.lexicon if isinstance(ctx.lexicon, SkillLexicon) else ctx.lexicon

    sentences_out: list = []
    claims_for_judge: list[Sentence] = []

    for ans in drafts.answers:
        for sent in ans.sentences:
            if sent.kind == "claim":
                sent.explanation = explain(sent, reqs, pool, lexicon)
            check = check_sentence(sent, pool, ctx)
            sentences_out.append(check)
            if sent.kind == "claim":
                claims_for_judge.append(sent)

    for sent in drafts.cover_note.sentences:
        if sent.kind == "claim":
            sent.explanation = explain(sent, reqs, pool, lexicon)
        check = check_sentence(sent, pool, ctx)
        sentences_out.append(check)
        if sent.kind == "claim":
            claims_for_judge.append(sent)

    if judge_enabled and judge is not None:
        sentences_out = await apply_judge(sentences_out, claims_for_judge, judge, outbound)

    return TruthReport(sentences=sentences_out, judge_enabled=judge_enabled)
