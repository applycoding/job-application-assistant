def test_stored_xss_escaped(client, repo, settings, fixed_clock, seq_ids):
    import hashlib

    from jaa.ingest.loaders import detect_media_type, load_lines

    payload = "<script>alert(1)</script>"
    data = payload.encode()
    mt = detect_media_type("evil.txt", data)
    lines, warnings = load_lines(data, mt)
    sha = hashlib.sha256(data).hexdigest()
    repo.upsert_document("evil.txt", "txt", sha, lines, warnings)
    r = client.raw.get("/")
    assert "<script>" not in r.text
