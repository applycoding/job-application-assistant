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
