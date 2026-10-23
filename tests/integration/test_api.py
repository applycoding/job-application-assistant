"""HTTP API surface (PLAN §5.10)."""

from __future__ import annotations

from pathlib import Path

from jaa.samples import seed

SAMPLES = Path("samples")


def test_healthz(raw_client):
    r = raw_client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"


def test_healthz_bad_host(raw_client):
    r = raw_client.get("/healthz", headers={"Host": "evil.example"})
    assert r.status_code == 400


def test_csrf_endpoint(raw_client):
    r = raw_client.get("/api/csrf")
    assert r.status_code == 200
    assert "token" in r.json()


def test_delete_data(client, repo):
    assert client.delete("/api/data").status_code == 204
    assert repo.list_documents() == []


def test_upload_and_list_documents(client, repo):
    data = (SAMPLES / "alex-doe-cv.md").read_bytes()
    r = client.post(
        "/api/documents",
        files={"file": ("alex-doe-cv.md", data, "application/octet-stream")},
    )
    assert r.status_code == 201
    doc_id = r.json()["id"]
    listed = client.get("/api/documents")
    assert listed.status_code == 200
    assert any(d["id"] == doc_id for d in listed.json())
    chunks = client.get(f"/api/documents/{doc_id}/chunks")
    assert chunks.status_code == 200
    assert len(chunks.json()) > 0


def test_document_not_found(client):
    assert client.get("/api/documents/missing/chunks").status_code == 404


def test_create_and_get_job(client, repo):
    text = (SAMPLES / "jobs/01-senior-data-engineer-acme-logistics.md").read_text()
    r = client.post("/api/jobs", json={"text": text})
    assert r.status_code == 201
    job_id = r.json()["id"]
    got = client.get(f"/api/jobs/{job_id}")
    assert got.status_code == 200
    assert got.json()["id"] == job_id


def test_job_empty_text_422(client):
    assert client.post("/api/jobs", json={"text": ""}).status_code == 422


def test_create_run_requires_documents(client):
    text = (SAMPLES / "jobs/01-senior-data-engineer-acme-logistics.md").read_text()
    job = client.post("/api/jobs", json={"text": text}).json()
    r = client.post(f"/api/jobs/{job['id']}/runs", json={})
    assert r.status_code == 409


def test_full_run_flow(client, app, settings, fixed_clock, seq_ids, repo):
    seed(repo, settings, fixed_clock, seq_ids, app.state.lexicon)
    job = next(j for j in repo.list_jobs() if "Acme" in j.title)
    preview = client.get(f"/api/jobs/{job.id}/outbound-preview")
    assert preview.status_code == 200
    run = client.post(f"/api/jobs/{job.id}/runs", json={})
    assert run.status_code == 201
    run_id = run.json()["id"]
    fetched = client.get(f"/api/runs/{run_id}")
    assert fetched.status_code == 200
    assert "stale" in fetched.json()
    pruned = client.post(f"/api/runs/{run_id}/prune")
    assert pruned.status_code == 201
    export_md = client.raw.get(f"/api/runs/{pruned.json()['id']}/export?format=md")
    assert export_md.status_code == 200
    assert export_md.headers.get("content-disposition", "").startswith("attachment")


def test_load_samples(client, repo):
    r = client.post("/api/samples/load")
    assert r.status_code == 200
    assert len(repo.list_documents()) == 4
    assert len(repo.list_jobs()) == 3


def test_mutations_forbidden_without_csrf(raw_client, repo, app, settings, fixed_clock, seq_ids):
    seed(repo, settings, fixed_clock, seq_ids, app.state.lexicon)
    job = repo.list_jobs()[0]
    assert raw_client.post(f"/api/jobs/{job.id}/runs", json={}).status_code == 403
    assert raw_client.post("/api/samples/load").status_code == 403
    assert raw_client.delete("/api/data").status_code == 403


def test_run_not_found(client):
    assert client.get("/api/runs/run-9999").status_code == 404
