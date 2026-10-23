"""Export runs as Markdown or JSON."""

from __future__ import annotations

import json
from html import escape

from jaa.models import Run


def is_stale(run: Run, current_corpus_version: str) -> bool:
    return run.corpus_version != current_corpus_version


def export_json(run: Run) -> str:
    data = run.model_dump(mode="json")

    def _round_floats(obj: object) -> object:
        if isinstance(obj, float):
            return round(obj, 6)
        if isinstance(obj, dict):
            return {k: _round_floats(v) for k, v in sorted(obj.items())}
        if isinstance(obj, list):
            return [_round_floats(v) for v in obj]
        return obj

    rounded = _round_floats(data)
    return json.dumps(rounded, indent=2, sort_keys=True, ensure_ascii=True)


def export_markdown(run: Run, *, citations: bool = True) -> str:
    lines: list[str] = []
    lines.append(f"# Run {escape(run.id)}")
    lines.append("")
    lines.append(f"**Job:** {escape(run.job_id)}")
    lines.append(f"**Badge:** {escape(run.report.badge_text)}")
    lines.append("")

    for ans in run.drafts.answers:
        lines.append(f"## {escape(ans.question_id)}: {escape(ans.question)}")
        for sent in ans.sentences:
            lines.append(_sentence_md(sent, run, citations=citations))
        lines.append("")

    lines.append("## Cover note")
    lines.append(escape(run.drafts.cover_note.salutation))
    lines.append("")
    for sent in run.drafts.cover_note.sentences:
        lines.append(_sentence_md(sent, run, citations=citations))
    lines.append("")
    lines.append(escape(run.drafts.cover_note.signoff))
    return "\n".join(lines)


def _sentence_md(sent, run: Run, *, citations: bool) -> str:
    check = next((s for s in run.report.sentences if s.sentence_id == sent.id), None)
    status = check.status if check else "checks_passed"
    prefix = "*" if sent.kind == "framing" else "-"
    text = escape(sent.text)
    line = f"{prefix} {text}"
    if citations and sent.citations:
        line += f" _(cites: {', '.join(escape(c) for c in sent.citations)})_"
    if sent.kind == "claim":
        line += f" `[{escape(status)}]`"
    return line
