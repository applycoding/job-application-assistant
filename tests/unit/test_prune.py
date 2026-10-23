from jaa.models import AnswerDraft, CoverNote, Drafts, Sentence, SentenceCheck, TruthReport
from jaa.truth.prune import prune_flagged


def test_prune_removes_flagged():
    drafts = Drafts(
        answers=[
            AnswerDraft(
                question_id="Q1",
                question="q",
                sentences=[
                    Sentence(
                        id="Q1.S1",
                        kind="claim",
                        text="a",
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
                sentence_id="Q1.S1", status="unsupported", failures=[], checks_run=[], judge=None
            )
        ],
        judge_enabled=False,
    )
    new, _ = prune_flagged(drafts, report)
    assert new.answers[0].sentences == []


def test_prune_keeps_clean_claims():
    drafts = Drafts(
        answers=[
            AnswerDraft(
                question_id="Q1",
                question="q",
                sentences=[
                    Sentence(
                        id="Q1.S1",
                        kind="claim",
                        text="keep",
                        citations=[],
                        requirement_ids=[],
                        rationale="",
                    ),
                    Sentence(
                        id="Q1.S2",
                        kind="claim",
                        text="drop",
                        citations=[],
                        requirement_ids=[],
                        rationale="",
                    ),
                ],
            )
        ],
        cover_note=CoverNote(salutation="Hi", sentences=[], signoff="Bye"),
    )
    report = TruthReport(
        sentences=[
            SentenceCheck(
                sentence_id="Q1.S1", status="checks_passed", failures=[], checks_run=[], judge=None
            ),
            SentenceCheck(
                sentence_id="Q1.S2", status="unsupported", failures=[], checks_run=[], judge=None
            ),
        ],
        judge_enabled=False,
    )
    new, _ = prune_flagged(drafts, report)
    assert [s.id for s in new.answers[0].sentences] == ["Q1.S1"]
