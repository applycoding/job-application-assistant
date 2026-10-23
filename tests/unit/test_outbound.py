from datetime import UTC

from jaa.models import RetrievalResult
from jaa.privacy.outbound import build_outbound_draft


def test_contact_chunks_not_in_outbound():
    from datetime import datetime

    from jaa.models import Chunk, JobPost, Question, Requirement

    job = JobPost(
        id="j",
        title="T",
        company="C",
        text="x",
        requirements=[
            Requirement(
                id="R1", text="Python", priority="must", skills=["Python"], terms=["python"]
            )
        ],
        questions=[Question(id="Q1", text="Q")],
        created_at=datetime.now(UTC),
    )
    Chunk(id="c1", doc_id="d", line_no=1, kind="bullet", text="python work", section="S")
    draft = build_outbound_draft(job, RetrievalResult(evidence=[], gaps=[]))
    assert draft.evidence == []
