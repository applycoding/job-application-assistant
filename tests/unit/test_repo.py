import hashlib
from pathlib import Path

from jaa.ingest.loaders import detect_media_type, load_lines


def test_upsert_and_replace(repo, settings):
    data = (Path("samples") / "alex-doe-cv.md").read_bytes()
    mt = detect_media_type("alex-doe-cv.md", data[:64])
    lines, warnings = load_lines(data, mt)
    sha = hashlib.sha256(data).hexdigest()
    d1 = repo.upsert_document("alex-doe-cv.md", mt, sha, lines, warnings)
    d2 = repo.upsert_document("alex-doe-cv.md", mt, sha, lines, warnings)
    assert d1.id == d2.id


def test_reingest_same_cv_bytes_keeps_chunk_ids(repo, settings):
    data = (Path("samples") / "alex-doe-cv.md").read_bytes()
    mt = detect_media_type("alex-doe-cv.md", data[:64])
    lines, warnings = load_lines(data, mt)
    sha = hashlib.sha256(data).hexdigest()
    d1 = repo.upsert_document("alex-doe-cv.md", mt, sha, lines, warnings)
    ids_before = {c.id for c in repo.get_chunks(d1.id)}
    repo.delete_document(d1.id)
    d2 = repo.upsert_document("alex-doe-cv.md", mt, sha, lines, warnings)
    assert d2.id != d1.id
    ids_after = {c.id for c in repo.get_chunks(d2.id)}
    assert ids_before == ids_after
    assert all(":" not in cid for cid in ids_before)
