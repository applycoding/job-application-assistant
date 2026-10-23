"""Playwright smoke test against subprocess server."""

from __future__ import annotations

import os
import socket
import subprocess
import time
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from tests.conftest import PLAYWRIGHT_BROWSERS_PATH

pytestmark = pytest.mark.e2e

ROOT = Path(__file__).resolve().parents[2]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def server_url(tmp_path_factory) -> str:
    tmp = tmp_path_factory.mktemp("e2e")
    db = tmp / "jaa.sqlite3"
    home = tmp / "home"
    home.mkdir()
    nonce = "e2e-nonce-123"
    port = _free_port()
    browsers = PLAYWRIGHT_BROWSERS_PATH
    env = {
        "PATH": os.environ.get("PATH", ""),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "HOME": str(home),
        "PLAYWRIGHT_BROWSERS_PATH": browsers,
        "JAA_PROVIDER": "mock",
        "JAA_DB_PATH": str(db),
        "JAA_REFERENCE_DATE": "2026-10-23",
        "JAA_INSTANCE_NONCE": nonce,
    }
    for key in list(os.environ):
        if key.endswith("_API_KEY") or key.endswith("_BASE_URL") or "PROXY" in key:
            assert key not in env
    log_dir = ROOT / "test-results"
    log_dir.mkdir(exist_ok=True)
    log = open(log_dir / "server.log", "w", encoding="utf-8")
    env["JAA_HOST"] = "127.0.0.1"
    env["JAA_PORT"] = str(port)
    proc = subprocess.Popen(
        [str(ROOT / ".venv/bin/jaa"), "serve"],
        cwd=str(ROOT),
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            import urllib.request

            with urllib.request.urlopen(f"{url}/healthz", timeout=1) as resp:
                body = resp.read().decode()
                if nonce in body:
                    break
        except OSError:
            time.sleep(0.2)
    else:
        proc.kill()
        raise RuntimeError("server did not become healthy")
    try:
        yield url
    finally:
        proc.terminate()
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_smoke_flow(server_url: str) -> None:
    aborted = 0
    errors: list[str] = []
    host = server_url.replace("http://", "").split("/")[0]

    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = PLAYWRIGHT_BROWSERS_PATH
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()

        def route_handler(route, request):  # type: ignore[no-untyped-def]
            nonlocal aborted
            if host not in request.url:
                aborted += 1
                route.abort()
            else:
                route.continue_()

        context.route("**/*", route_handler)
        page = context.new_page()
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        shot_dir = ROOT / "docs" / "screenshots"
        update_shots = os.environ.get("JAA_UPDATE_SCREENSHOTS") == "1"
        page.goto(server_url + "/")
        if update_shots:
            shot_dir.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(shot_dir / "home.png"), full_page=True)
        page.get_by_test_id("load-samples").click()
        page.get_by_test_id("job-link").first.click()
        if update_shots:
            page.screenshot(path=str(shot_dir / "job.png"), full_page=True)
        assert page.get_by_test_id("outbound-preview").count() == 0
        page.get_by_test_id("generate-button").click()
        page.wait_for_url("**/runs/**")
        assert page.locator("[data-testid=claim][data-status=unsupported]").count() == 1
        badge = page.get_by_test_id("truth-badge").inner_text()
        assert "1 unsupported" in badge
        if update_shots:
            page.screenshot(path=str(shot_dir / "run-unsupported.png"), full_page=True)
        page.locator("[data-testid=claim][data-status=unsupported] summary").click()
        reasons = page.locator("[data-testid=claim][data-status=unsupported]").inner_text()
        assert "Initech" in reasons and "15" in reasons
        page.get_by_test_id("prune-button").click()
        page.wait_for_url("**/runs/**")
        assert page.locator("[data-testid=claim][data-status=unsupported]").count() == 0
        assert "No deterministic issues found" in page.get_by_test_id("truth-badge").inner_text()
        if update_shots:
            page.screenshot(path=str(shot_dir / "run-pruned.png"), full_page=True)
        browser.close()
    assert aborted == 0
    assert errors == []
