from datetime import UTC, datetime

from jaa.export import export_markdown
from jaa.models import (
    AnswerDraft,
    CoverNote,
    Drafts,
    Run,
    Sentence,
    SentenceCheck,
    TruthReport,
)


def _minimal_run() -> Run:
    drafts = Drafts(
        answers=[
            AnswerDraft(
                question_id="Q1",
                question="q",
                sentences=[
                    Sentence(
                        id="Q1.S1",
                        kind="claim",
                        text="safe <b>",
                        citations=[],
                        requirement_ids=[],
                        rationale="",
                    )
                ],
            )
        ],
        cover_note=CoverNote(salutation="Hi", sentences=[], signoff="Bye"),
    )
    report = TruthReport(
        sentences=[
            SentenceCheck(
                sentence_id="Q1.S1",
                status="checks_passed",
                failures=[],
                checks_run=[],
                judge=None,
            )
        ],
        judge_enabled=False,
    )
    return Run(
        id="run-0001",
        job_id="job-x",
        parent_run_id=None,
        created_at=datetime(2026, 10, 23, 9, 0, tzinfo=UTC),
        provider="mock",
        model="mock-1",
        judge_model=None,
        judge_enabled=False,
        corpus_version="v1",
        check_rules_version="2026-10-23.1",
        requirements=[],
        evidence=[],
        gaps=[],
        drafts=drafts,
        report=report,
        warnings=[],
    )


def test_export_markdown_escapes() -> None:
    md = export_markdown(_minimal_run())
    assert "<b>" not in md
    assert "&lt;b&gt;" in md
