"""Long seeded scenario (PLAN §7.4) — 21 steps."""

from __future__ import annotations

from pathlib import Path

import pytest

from jaa.providers.mock import INJECTED_CLAIM, MockProvider
from jaa.retrieval.service import retrieve_for_job
from jaa.truth.lexicon import SkillLexicon

pytestmark = pytest.mark.scenario

SAMPLES = Path("samples")


class CountingMock(MockProvider):
    def __init__(self) -> None:
        super().__init__()
        self.draft_calls = 0
        self.judge_calls = 0

    async def draft(self, req):  # type: ignore[no-untyped-def]
        self.draft_calls += 1
        return await super().draft(req)

    async def judge(self, req):  # type: ignore[no-untyped-def]
        self.judge_calls += 1
        return await super().judge(req)


@pytest.fixture
def counting_app(app, settings):
    provider = CountingMock()
    app.state.provider = provider
    return app, provider


def _upload(client, name: str) -> dict:
    data = (SAMPLES / name).read_bytes()
    r = client.post(
        "/api/documents",
        files={"file": (name, data, "application/octet-stream")},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _job_text(n: int) -> str:
    return (SAMPLES / "jobs" / f"{n:02d}-").read_text()  # placeholder


def test_full_session_21_steps(counting_app, client, repo, settings, fixed_clock, seq_ids):
    app, provider = counting_app
    lex = SkillLexicon.load(None)

    # 1
    assert client.delete("/api/data").status_code == 204
    assert repo.list_documents() == []
    assert repo.list_jobs() == []

    # 2
    doc_cv = _upload(client, "alex-doe-cv.md")
    chunks_cv = repo.get_chunks(doc_cv["id"])
    contact = [c for c in chunks_cv if c.kind == "contact"]
    assert len(contact) >= 2
    assert any(c.text.strip() == "Go" or "Go" in c.text for c in chunks_cv if c.kind != "contact")

    # 3
    _upload(client, "alex-doe-projects.txt")
    _upload(client, "alex-doe-certificates.pdf")
    _upload(client, "alex-doe-volunteering.docx")
    assert len(repo.list_documents()) == 4

    # 4 re-upload cv
    doc_cv2 = _upload(client, "alex-doe-cv.md")
    assert doc_cv2["id"] == doc_cv["id"]

    # 5 duplicate sha new name
    data = (SAMPLES / "alex-doe-cv.md").read_bytes()
    r = client.post(
        "/api/documents",
        files={"file": ("alex-doe-cv-copy.md", data, "application/octet-stream")},
    )
    assert r.status_code == 409

    # 6 jobs
    for rel in (
        "jobs/01-senior-data-engineer-acme-logistics.md",
        "jobs/02-ml-platform-engineer-globex-energy.md",
        "jobs/03-backend-python-developer-vandelay-health.md",
    ):
        text = (SAMPLES / rel).read_text(encoding="utf-8")
        r = client.post("/api/jobs", json={"text": text})
        assert r.status_code == 201

    jobs = repo.list_jobs()
    assert len(jobs) == 3
    job01 = next(j for j in jobs if "Acme" in j.title)
    job02 = next(j for j in jobs if "Globex" in j.title)
    job03 = next(j for j in jobs if "Vandelay" in j.title)

    # 7 gaps
    chunks = repo.get_chunks(retrievable_only=True)
    g2 = retrieve_for_job(job02, chunks, lex).gaps
    assert any(g.requirement_id and g.term is None for g in g2)
    g3 = retrieve_for_job(job03, chunks, lex).gaps
    assert any(g.term == "FastAPI" for g in g3 if g.term)

    # 8 generate job01
    r = client.post(f"/api/jobs/{job01.id}/runs", json={})
    assert r.status_code == 201
    run1 = repo.get_run("run-0001")
    flagged = [s for s in run1.report.sentences if s.status == "unsupported"]
    assert len(flagged) == 1
    inj = next(s for s in run1.drafts.cover_note.sentences if s.text == INJECTED_CLAIM)
    inj_check = next(s for s in run1.report.sentences if s.sentence_id == inj.id)
    assert inj_check.status == "unsupported"
    assert "1 unsupported" in run1.report.badge_text

    # 9 prune -> run-0002
    calls_before = provider.draft_calls
    r = client.post("/api/runs/run-0001/prune")
    assert r.status_code == 201
    run2 = repo.get_run("run-0002")
    assert run2.parent_run_id == "run-0001"
    assert run2.report.unsupported == 0
    assert provider.draft_calls == calls_before

    # 10 prune again -> run-0003
    client.post("/api/runs/run-0002/prune")
    run3 = repo.get_run("run-0003")
    assert run3.report.badge_text == "No deterministic issues found"

    # 11 job02
    client.post(f"/api/jobs/{job02.id}/runs", json={})
    # 12 job02 judge on
    client.post(f"/api/jobs/{job02.id}/runs", json={"judge": True})
    run5 = repo.get_run("run-0005")
    assert run5.judge_enabled
    assert provider.judge_calls == 1

    # 13 job03
    client.post(f"/api/jobs/{job03.id}/runs", json={})

    # 14 edit cv bullet
    cv_path = SAMPLES / "alex-doe-cv.md"
    original = cv_path.read_text(encoding="utf-8")
    edited = original.replace("cut runtime by 40%", "cut runtime by 41%")
    r = client.post(
        "/api/documents",
        files={"file": ("alex-doe-cv.md", edited.encode(), "application/octet-stream")},
    )
    assert r.status_code == 201
    for rid in ("run-0001", "run-0006"):
        run = repo.get_run(rid)
        from jaa.export import is_stale

        cur, _ = repo.corpus_snapshot(settings.reference_date)
        assert is_stale(run, cur)

    # 15 delete volunteering doc
    vol = next(d for d in repo.list_documents() if "volunteering" in d.filename)
    r = client.delete(f"/api/documents/{vol.id}?delete_runs=false")
    assert r.json()["deleted_runs"] == 0
    assert len(repo.list_documents()) == 3

    # 16 old runs still readable
    for i in range(1, 7):
        assert client.raw.get(f"/api/runs/run-{i:04d}").status_code == 200

    # 17 generate job01 again
    client.post(f"/api/jobs/{job01.id}/runs", json={})
    run7 = repo.get_run("run-0007")
    assert vol.id not in {
        c for s in run7.drafts.answers for sent in s.sentences for c in sent.citations
    }

    # 18 prune run7
    client.post("/api/runs/run-0007/prune")

    # 19 export run8
    md = client.raw.get("/api/runs/run-0008/export?format=md")
    assert md.status_code == 200
    assert "attachment" in md.headers.get("content-disposition", "")

    # 20 healthz
    hz = client.raw.get("/healthz").json()
    assert hz["status"] == "ok" and hz["provider"] == "mock"

    # 21 totals
    assert len(repo.list_documents()) == 3
    assert len(repo.list_jobs()) == 3
    runs = [repo.get_run(f"run-{i:04d}") for i in range(1, 9)]
    assert len(runs) == 8
    assert provider.draft_calls == 5
    assert provider.judge_calls == 1
