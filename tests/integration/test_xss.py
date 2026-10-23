import hashlib

from jaa.ingest.loaders import detect_media_type, load_lines


def test_stored_xss_escaped_on_document_page(client, repo):
    payload = "<script>alert(1)</script>"
    data = payload.encode()
    mt = detect_media_type("evil.txt", data)
    lines, warnings = load_lines(data, mt)
    sha = hashlib.sha256(data).hexdigest()
    repo.upsert_document("evil.txt", "txt", sha, lines, warnings)
    doc_id = repo.list_documents()[-1].id
    r = client.raw.get(f"/documents/{doc_id}")
    assert r.status_code == 200
    assert "<script>" not in r.text
    assert "&lt;script&gt;" in r.text


def test_xss_escaped_on_run_page_and_export(client, app, settings, fixed_clock, seq_ids, repo):
    seed = __import__("jaa.samples", fromlist=["seed"]).seed
    seed(repo, settings, fixed_clock, seq_ids, app.state.lexicon)
    payload = "<img src=x onerror=alert(1)>"
    data = payload.encode()
    mt = detect_media_type("xss.txt", data)
    lines, warnings = load_lines(data, mt)
    sha = hashlib.sha256(data).hexdigest()
    repo.upsert_document("xss.txt", "txt", sha, lines, warnings)
    job = repo.list_jobs()[0]
    run = client.post(f"/api/jobs/{job.id}/runs", json={})
    assert run.status_code == 201
    run_id = run.json()["id"]
    page = client.raw.get(f"/runs/{run_id}")
    assert page.status_code == 200
    assert "onerror=alert" not in page.text
    export = client.raw.get(f"/api/runs/{run_id}/export?format=md")
    assert export.status_code == 200
    assert "onerror=alert" not in export.text
