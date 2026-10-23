"""Host, Origin, CSRF and header security tests."""

from starlette.testclient import TestClient


def test_bad_host_returns_400(raw_client: TestClient) -> None:
    r = raw_client.get("/healthz", headers={"Host": "evil.example"})
    assert r.status_code == 400


def test_cross_origin_post_forbidden(raw_client: TestClient, client) -> None:
    r = raw_client.delete(
        "/api/data",
        headers={"Origin": "http://evil.example:8000", "X-CSRF-Token": "nope"},
    )
    assert r.status_code == 403


def test_missing_csrf_forbidden(client) -> None:
    r = client.raw.delete(
        "/api/data",
        headers={"Origin": "http://127.0.0.1:8000"},
    )
    assert r.status_code == 403


def test_valid_csrf_delete(client) -> None:
    r = client.delete("/api/data")
    assert r.status_code == 204


def test_csp_and_nosiff_present(raw_client: TestClient) -> None:
    r = raw_client.get("/healthz")
    assert "Content-Security-Policy" in r.headers
    assert r.headers.get("X-Content-Type-Options") == "nosniff"


def test_no_cors_on_options(raw_client: TestClient) -> None:
    r = raw_client.options(
        "/api/jobs",
        headers={
            "Origin": "http://127.0.0.1:8000",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}
