"""Long seeded scenario (PLAN §7.4) — 21 steps with goldens."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from jaa.export import export_json, export_markdown, is_stale
from jaa.providers.mock import INJECTED_CLAIM
from jaa.retrieval.service import retrieve_for_job
from jaa.truth.lexicon import SkillLexicon

pytestmark = pytest.mark.scenario

SAMPLES = Path("samples")
GOLDEN = Path("tests/golden")
UPDATE = os.environ.get("JAA_UPDATE_GOLDEN") == "1"


class CountingMock:
    def __init__(self, inner) -> None:  # type: ignore[no-untyped-def]
        self._inner = inner
        self.draft_calls = 0
        self.judge_calls = 0

    async def draft(self, req):  # type: ignore[no-untyped-def]
        self.draft_calls += 1
        return await self._inner.draft(req)

    async def judge(self, req):  # type: ignore[no-untyped-def]
        self.judge_calls += 1
        return await self._inner.judge(req)

    def __getattr__(self, name: str):  # type: ignore[no-untyped-def]
        return getattr(self._inner, name)


@pytest.fixture
def counting_app(app):
    from jaa.providers.mock import MockProvider

    inner = MockProvider()
    provider = CountingMock(inner)
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


def _failures_set(check) -> set[tuple[str, str | None]]:
    return {(f.check, f.token) for f in check.failures}


def test_full_session_21_steps(
    counting_app, client, repo, settings, fixed_clock, seq_ids, raw_client
):
    _app, provider = counting_app
    lex = SkillLexicon.load(None)
    ref = settings.reference_date
    assert ref is not None

    # 1 — fresh DB
    assert client.delete("/api/data").status_code == 204
    assert repo.list_documents() == []
    assert repo.list_jobs() == []

    # 2 — CV upload
    doc_cv = _upload(client, "alex-doe-cv.md")
    chunks_cv = repo.get_chunks(doc_cv["id"])
    contact = [c for c in chunks_cv if c.kind == "contact"]
    assert len(contact) >= 2
    counts_path = GOLDEN / "scenario_cv_chunks.json"
    if UPDATE or not counts_path.is_file():
        counts_path.write_text(
            json.dumps({"chunk_count": len(chunks_cv), "contact_chunks": len(contact)}, indent=2)
            + "\n",
            encoding="utf-8",
        )
    else:
        expected = json.loads(counts_path.read_text(encoding="utf-8"))
        assert len(chunks_cv) == expected["chunk_count"]
        assert len(contact) == expected["contact_chunks"]

    # 3 — other samples
    _upload(client, "alex-doe-projects.txt")
    _upload(client, "alex-doe-certificates.pdf")
    _upload(client, "alex-doe-volunteering.docx")
    assert len(repo.list_documents()) == 4
    # 4 — re-upload unchanged CV
    doc_cv2 = _upload(client, "alex-doe-cv.md")
    assert doc_cv2["id"] == doc_cv["id"]
    ids_before = {c.id for c in repo.get_chunks(doc_cv["id"])}
    ids_after = {c.id for c in repo.get_chunks(doc_cv2["id"])}
    assert ids_before == ids_after

    # 5 — duplicate sha, new filename
    data = (SAMPLES / "alex-doe-cv.md").read_bytes()
    r = client.post(
        "/api/documents",
        files={"file": ("alex-doe-cv-copy.md", data, "application/octet-stream")},
    )
    assert r.status_code == 409

    # 6 — jobs
    for rel in (
        "jobs/01-senior-data-engineer-acme-logistics.md",
        "jobs/02-ml-platform-engineer-globex-energy.md",
        "jobs/03-backend-python-developer-vandelay-health.md",
    ):
        text = (SAMPLES / rel).read_text(encoding="utf-8")
        assert client.post("/api/jobs", json={"text": text}).status_code == 201
    jobs = repo.list_jobs()
    assert len(jobs) == 3
    job01 = next(j for j in jobs if "Acme" in j.title)
    job02 = next(j for j in jobs if "Globex" in j.title)
    job03 = next(j for j in jobs if "Vandelay" in j.title)

    # 7 — gaps
    chunks = repo.get_chunks(retrievable_only=True)
    g2 = retrieve_for_job(job02, chunks, lex).gaps
    ml_req = next(r for r in job02.requirements if "mlflow" in r.text.lower())
    assert any(g.requirement_id == ml_req.id and g.term is None for g in g2)
    g3 = retrieve_for_job(job03, chunks, lex).gaps
    py_go = next(r for r in job03.requirements if "Go" in r.skills and "Python" in r.skills)
    assert any(g.requirement_id == py_go.id and g.term == "Go" for g in g3)

    # 8 — job01 run-0001
    assert client.post(f"/api/jobs/{job01.id}/runs", json={}).status_code == 201
    run1 = repo.get_run("run-0001")
    inj = next(s for s in run1.drafts.cover_note.sentences if s.text == INJECTED_CLAIM)
    inj_check = next(s for s in run1.report.sentences if s.sentence_id == inj.id)
    assert inj_check.status == "unsupported"
    assert _failures_set(inj_check) == {("employer", "Initech"), ("number", "15")}
    assert run1.report.unsupported == 1
    assert run1.report.not_verified == 0
    n_claims = run1.report.claims
    assert run1.report.badge_text == f"1 unsupported, 0 not verified (of {n_claims} claims)"
    for sc in run1.report.sentences:
        if sc.sentence_id == inj.id:
            continue
        if sc.sentence_id.startswith("C.F"):
            continue
        assert sc.status == "checks_passed"

    # 9 — prune run-0002
    calls_before = provider.draft_calls
    assert client.post("/api/runs/run-0001/prune").status_code == 201
    run2 = repo.get_run("run-0002")
    assert run2.parent_run_id == "run-0001"
    assert run2.report.unsupported + run2.report.not_verified == 0
    assert len(run2.drafts.cover_note.sentences) == len(run1.drafts.cover_note.sentences) - 1
    assert provider.draft_calls == calls_before

    # 10 — prune run-0003 idempotent
    client.post("/api/runs/run-0002/prune")
    run3 = repo.get_run("run-0003")
    assert run3.parent_run_id == "run-0002"
    assert run3.report.badge_text == "No deterministic issues found"
    assert run3.drafts.model_dump() == run2.drafts.model_dump()

    # 11 — job02 run-0004
    client.post(f"/api/jobs/{job02.id}/runs", json={})
    run4 = repo.get_run("run-0004")

    # 12 — job02 judge run-0005
    client.post(f"/api/jobs/{job02.id}/runs", json={"judge": True})
    run5 = repo.get_run("run-0005")
    assert run5.judge_enabled
    assert provider.judge_calls == 1
    r4_fail = {s.sentence_id: s.status for s in run4.report.sentences if s.failures}
    r5_fail = {s.sentence_id: s.status for s in run5.report.sentences if s.failures}
    assert r4_fail == r5_fail
    inj5 = next(s for s in run5.drafts.cover_note.sentences if s.text == INJECTED_CLAIM)
    inj5_check = next(s for s in run5.report.sentences if s.sentence_id == inj5.id)
    assert inj5_check.judge is None
    for sc in run5.report.sentences:
        if sc.failures or sc.sentence_id.startswith("C.F") or sc.sentence_id == inj5.id:
            continue
        assert sc.status == "entailed"

    # 13 — job03 run-0006
    client.post(f"/api/jobs/{job03.id}/runs", json={})
    run6 = repo.get_run("run-0006")
    pool_golden = GOLDEN / "job03_pool.json"
    pool_dump = [{"chunk_id": e.chunk.id, "score": round(e.score, 6)} for e in run6.evidence]
    if UPDATE or not pool_golden.is_file():
        pool_golden.write_text(json.dumps(pool_dump, indent=2) + "\n", encoding="utf-8")
    else:
        assert pool_dump == json.loads(pool_golden.read_text(encoding="utf-8"))

    # 14 — edit CV bullet, corpus version changes, runs 1-6 stale
    cv_text = (SAMPLES / "alex-doe-cv.md").read_text(encoding="utf-8")
    edited = cv_text.replace("cut runtime by 40%", "cut runtime by 41%")
    assert (
        client.post(
            "/api/documents",
            files={"file": ("alex-doe-cv.md", edited.encode(), "application/octet-stream")},
        ).status_code
        == 201
    )
    cur_ver_after_edit, _ = repo.corpus_snapshot(ref)
    for i in range(1, 7):
        assert is_stale(repo.get_run(f"run-{i:04d}"), cur_ver_after_edit)

    # 15 — delete volunteering, keep runs
    vol = next(d for d in repo.list_documents() if "volunteering" in d.filename)
    r = client.delete(f"/api/documents/{vol.id}?delete_runs=false")
    assert r.json()["deleted_runs"] == 0
    assert len(repo.list_documents()) == 3
    cur_ver, _ = repo.corpus_snapshot(ref)

    # 16 — old runs still load with stale flag
    for i in range(1, 7):
        payload = client.raw.get(f"/api/runs/run-{i:04d}").json()
        assert payload["stale"] is True

    # 17 — job01 run-0007
    client.post(f"/api/jobs/{job01.id}/runs", json={})
    run7 = repo.get_run("run-0007")
    assert run7.corpus_version == cur_ver
    assert is_stale(run7, cur_ver) is False
    cited = {c for ans in run7.drafts.answers for sent in ans.sentences for c in sent.citations}
    assert not any(vol.id in cid for cid in cited)
    inj7 = next(s for s in run7.report.sentences if s.status == "unsupported")
    assert _failures_set(inj7) == {("employer", "Initech"), ("number", "15")}

    # 18 — prune run-0008
    client.post("/api/runs/run-0007/prune")
    run8 = repo.get_run("run-0008")
    assert run8.parent_run_id == "run-0007"

    # 19 — export run-0008 goldens
    md = export_markdown(run8)
    js = export_json(run8)
    md_path = GOLDEN / "scenario_final.md"
    js_path = GOLDEN / "scenario_final.json"
    if UPDATE:
        md_path.write_text(md, encoding="utf-8")
        js_path.write_text(js + ("\n" if not js.endswith("\n") else ""), encoding="utf-8")
    else:
        assert md == md_path.read_text(encoding="utf-8")
        assert js.strip() == js_path.read_text(encoding="utf-8").strip()
    exp = client.raw.get("/api/runs/run-0008/export?format=md")
    assert exp.status_code == 200
    assert "attachment" in exp.headers.get("content-disposition", "")

    # 20 — healthz
    hz = raw_client.get("/healthz").json()
    assert hz["status"] == "ok" and hz["provider"] == "mock"

    # 21 — totals
    assert len(repo.list_documents()) == 3
    assert len(repo.list_jobs()) == 3
    assert len([repo.get_run(f"run-{i:04d}") for i in range(1, 9)]) == 8
    assert provider.draft_calls == 5
    assert provider.judge_calls == 1
    unsupported_in_db = sum(
        1
        for i in range(1, 9)
        for s in repo.get_run(f"run-{i:04d}").report.sentences
        if s.status == "unsupported"
    )
    assert unsupported_in_db == 5
    assert (
        sum(
            1
            for i in range(1, 9)
            for s in repo.get_run(f"run-{i:04d}").report.sentences
            if s.status == "not_verified"
        )
        == 0
    )
    stale_runs = sum(1 for i in range(1, 7) if is_stale(repo.get_run(f"run-{i:04d}"), cur_ver))
    assert stale_runs == 6
