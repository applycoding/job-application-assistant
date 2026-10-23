from jaa.privacy.outbound import build_outbound_draft
from jaa.privacy.redact import redact
from jaa.retrieval.service import retrieve_for_job
from jaa.samples import seed


def test_redact_strips_email() -> None:
    assert "secret" not in redact("email secret@x.com")


def test_outbound_preview_redacts_contact(app, settings, repo, fixed_clock, seq_ids):
    seed(repo, settings, fixed_clock, seq_ids, app.state.lexicon)
    job = repo.list_jobs()[0]
    chunks = repo.get_chunks(retrievable_only=True)
    result = retrieve_for_job(job, chunks, app.state.lexicon)
    draft = build_outbound_draft(job, result)
    blob = draft.model_dump_json()
    assert "alex.doe@example.com" not in blob
    assert "555-0102" not in blob
    assert all("@" not in e.text for e in draft.evidence)
