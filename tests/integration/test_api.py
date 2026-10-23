def test_healthz(raw_client):
    r = raw_client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_csrf_endpoint(raw_client):
    r = raw_client.get("/api/csrf")
    assert "token" in r.json()


def test_delete_data(client):
    assert client.delete("/api/data").status_code == 204
