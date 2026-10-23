import hashlib
from pathlib import Path

from jaa.ingest.loaders import detect_media_type, load_lines

XSS_CANARY = "XSS_MARK_TOKEN"
XSS_PAYLOAD = f"Python streaming {XSS_CANARY} <img src=x onerror=alert(1)> experience"


def _cited_chunk_texts(repo, run) -> list[str]:
    ids = {
        cid for block in run.drafts.answers for sent in block.sentences for cid in sent.citations
    }
    ids |= {cid for sent in run.drafts.cover_note.sentences for cid in sent.citations}
    by_id = {c.id: c for c in repo.get_chunks()}
    return [by_id[cid].text for cid in ids if cid in by_id]


def test_stored_xss_escaped_on_document_page(client, repo):
    data = XSS_PAYLOAD.encode()
    mt = detect_media_type("evil.txt", data)
    lines, warnings = load_lines(data, mt)
    sha = hashlib.sha256(data).hexdigest()
    repo.upsert_document("evil.txt", "txt", sha, lines, warnings)
    doc_id = repo.list_documents()[-1].id
    r = client.raw.get(f"/documents/{doc_id}")
    assert r.status_code == 200
    assert XSS_CANARY in r.text
    assert "<img" not in r.text


def test_xss_escaped_on_run_page_and_export(client, repo, settings):
    client.delete("/api/data")
    data = XSS_PAYLOAD.encode()
    mt = detect_media_type("xss.txt", data)
    lines, warnings = load_lines(data, mt)
    sha = hashlib.sha256(data).hexdigest()
    repo.upsert_document("xss.txt", "txt", sha, lines, warnings)
    job_text = Path("samples/jobs/03-backend-python-developer-vandelay-health.md").read_text()
    job = client.post("/api/jobs", json={"text": job_text}).json()
    run = client.post(f"/api/jobs/{job['id']}/runs", json={})
    assert run.status_code == 201
    run_id = run.json()["id"]
    stored = repo.get_run(run_id)
    cited = _cited_chunk_texts(repo, stored)
    assert cited
    assert any(XSS_CANARY in t for t in cited)
    page = client.raw.get(f"/runs/{run_id}")
    assert page.status_code == 200
    assert "<img" not in page.text
    assert "onerror=alert" not in page.text
    export = client.raw.get(f"/api/runs/{run_id}/export?format=md")
    assert export.status_code == 200
    assert "onerror=alert" not in export.text
    assert "<img" not in export.text


def test_run_page_would_leak_without_autoescape(client, repo, settings):
    from jinja2 import Environment

    client.delete("/api/data")
    data = XSS_PAYLOAD.encode()
    mt = detect_media_type("xss2.txt", data)
    lines, warnings = load_lines(data, mt)
    sha = hashlib.sha256(data).hexdigest()
    repo.upsert_document("xss2.txt", "txt", sha, lines, warnings)
    job_text = Path("samples/jobs/03-backend-python-developer-vandelay-health.md").read_text()
    job = client.post("/api/jobs", json={"text": job_text}).json()
    run_id = client.post(f"/api/jobs/{job['id']}/runs", json={}).json()["id"]
    stored = repo.get_run(run_id)
    raw_line = next(t for t in _cited_chunk_texts(repo, stored) if XSS_CANARY in t)
    unsafe = Environment(autoescape=False).from_string("{{ t }}").render(t=raw_line)
    assert "onerror=alert" in unsafe
    page = client.raw.get(f"/runs/{run_id}")
    assert "onerror=alert" not in page.text
