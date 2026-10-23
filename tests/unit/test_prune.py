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
