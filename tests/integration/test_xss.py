"""Stored XSS in job metadata must render escaped on HTML and exports."""

from __future__ import annotations

import html

import pytest

from jaa.samples import seed
from jaa.web import routes_html

XSS_IMG = "<img src=x onerror=alert(1)>"
XSS_TITLE_MARK = "XSSTITLEMARK"
XSS_COMPANY_MARK = "XSSCOMPANYMARK"


def _job_post_text() -> str:
    return f"""# Backend Dev {XSS_TITLE_MARK} {XSS_IMG} - Vandelay {XSS_COMPANY_MARK} {XSS_IMG}

## Requirements
- Python backend services

## Application questions
1. What relevant experience do you bring?
"""


def _assert_html_safe(body: str) -> None:
    assert XSS_TITLE_MARK in body
    assert XSS_COMPANY_MARK in body
    assert html.escape(XSS_IMG) in body
    assert XSS_IMG not in body
    assert "<img" not in body


def _assert_export_safe(body: str) -> None:
    assert XSS_TITLE_MARK in body
    assert XSS_COMPANY_MARK in body
    assert XSS_IMG not in body
    assert "<img" not in body


@pytest.fixture
def xss_job(client, repo, settings, fixed_clock, seq_ids, app):
    seed(repo, settings, fixed_clock, seq_ids, app.state.lexicon)
    job = client.post("/api/jobs", json={"text": _job_post_text()}).json()
    run = client.post(f"/api/jobs/{job['id']}/runs", json={})
    assert run.status_code == 201
    return job["id"], run.json()["id"]


def test_xss_escaped_on_run_job_home_and_export(client, xss_job):
    job_id, run_id = xss_job
    for path in (f"/runs/{run_id}", f"/jobs/{job_id}", "/"):
        page = client.raw.get(path)
        assert page.status_code == 200
        _assert_html_safe(page.text)
    export = client.raw.get(f"/api/runs/{run_id}/export?format=md")
    assert export.status_code == 200
    _assert_export_safe(export.text)


def test_xss_protection_requires_template_autoescape(client, xss_job):
    from jinja2 import Environment, FileSystemLoader

    job_id, run_id = xss_job
    template_dir = routes_html.templates.env.loader.searchpath[0]
    original_env = routes_html.templates.env
    routes_html.templates.env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=False,
    )
    try:
        page = client.raw.get(f"/runs/{run_id}")
        assert XSS_IMG in page.text
        with pytest.raises(AssertionError):
            _assert_html_safe(page.text)
    finally:
        routes_html.templates.env = original_env
    page = client.raw.get(f"/jobs/{job_id}")
    _assert_html_safe(page.text)
