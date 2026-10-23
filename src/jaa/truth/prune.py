"""Remove flagged claims without provider calls."""

from __future__ import annotations

from jaa.models import Drafts, Sentence, TruthReport


def prune_flagged(drafts: Drafts, report: TruthReport) -> tuple[Drafts, list[str]]:
    flagged = set(report.flagged_ids)
    warnings: list[str] = []

    new_answers = []
    for i, ans in enumerate(drafts.answers, start=1):
        kept = [s for s in ans.sentences if s.id not in flagged]
        if not kept:
            warnings.append(f"Q{i}: no supported content - answer manually")
        new_answers.append(
            ans.model_copy(update={"sentences": kept}),
        )

    cover_kept: list[Sentence] = []
    claims_removed = False
    for sent in drafts.cover_note.sentences:
        if sent.kind == "framing" or sent.id not in flagged:
            cover_kept.append(sent)
        else:
            claims_removed = True

    if claims_removed and not any(s.kind == "claim" for s in cover_kept):
        warnings.append("Cover note has no supported claims - add manually")

    new_cover = drafts.cover_note.model_copy(update={"sentences": cover_kept})
    return Drafts(answers=new_answers, cover_note=new_cover), warnings
