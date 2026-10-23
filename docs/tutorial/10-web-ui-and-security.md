---
modules: src/jaa/web/security.py
checkpoint: uv run pytest tests/integration/test_html.py tests/integration/test_security.py tests/integration/test_xss.py
---

# Web UI and security

## Goal

See how the browser UI is served safely on localhost: CSRF tokens, host allowlists, strict Content-Security-Policy, and integration tests for XSS.

## Files

- `src/jaa/web/security.py` implements `HostAndHeadersMiddleware` and CSRF validation.
- `src/jaa/web/routes_html.py` renders pages with escaped user content.
- `src/jaa/web/routes_api.py` exposes JSON endpoints for ingest, jobs, and runs.
- `src/jaa/web/deps.py` shares repository and settings access with route handlers.

## Concepts

Mutating HTTP methods require a matching `Origin` or `Referer` from `localhost` / `127.0.0.1` on the configured port, plus a CSRF header tied to `app.state.csrf_token` generated at startup.

Responses add `Content-Security-Policy` with `default-src 'self'`, deny framing, and set `X-Content-Type-Options: nosniff`. Host headers outside the allowlist receive 400 responses to reduce DNS rebinding risk during local dev.

HTML routes should never interpolate raw job or draft text into script contexts; integration tests in `test_xss.py` guard regressions.

## Code walkthrough

Read `HostAndHeadersMiddleware.dispatch()`: host check runs first, security headers attach to every response, and CSRF logic gates POST-like API calls.

Compare `_origin_urls()` with `Settings.public_port` when running behind Docker port publishing so Origin checks still match what the browser sends.

## Checkpoint

Run: `uv run pytest tests/integration/test_html.py tests/integration/test_security.py tests/integration/test_xss.py`

## Exercise

Start `uv run jaa serve` and confirm form posts include the CSRF token from the HTML template. Attempt a curl POST without the token and observe the rejected response status documented in tests.

Browse `routes_api.py` and name one read-only GET endpoint that does not require CSRF but still benefits from security headers.
