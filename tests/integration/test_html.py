def test_index_renders(raw_client):
    r = raw_client.get("/")
    assert r.status_code == 200
    assert "Job Application Assistant" in r.text or "Alex" in r.text
