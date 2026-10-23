"""Host allowlist, Origin + CSRF checks, and security response headers."""

from __future__ import annotations

import hmac
import secrets
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

if TYPE_CHECKING:
    from jaa.config import Settings

MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

CSP = (
    "default-src 'self'; script-src 'self'; object-src 'none'; "
    "base-uri 'none'; frame-ancestors 'none'"
)

SECURITY_HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
}


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def allowed_hostnames() -> frozenset[str]:
    return frozenset({"localhost", "127.0.0.1"})


def hostname_from_host_header(host: str) -> str:
    value = host.strip().lower()
    if not value:
        return ""
    if value.startswith("["):
        end = value.find("]")
        if end != -1:
            return value[1:end]
    if value.count(":") > 1 and ":" in value:
        return value.split(":")[0]
    return value.rsplit(":", 1)[0]


def is_allowed_host(host_header: str | None) -> bool:
    if not host_header:
        return False
    return hostname_from_host_header(host_header) in allowed_hostnames()


def _origin_urls(settings: Settings) -> frozenset[str]:
    port = settings.public_port if settings.public_port is not None else settings.port
    return frozenset(
        {
            f"http://localhost:{port}",
            f"http://127.0.0.1:{port}",
        }
    )


def _origin_from_request(request: Request) -> str | None:
    origin = request.headers.get("origin")
    if origin:
        return origin.strip()
    referer = request.headers.get("referer")
    if not referer:
        return None
    referer = referer.strip()
    for sep in ("/", "?", "#"):
        idx = referer.find(sep, len("http://"))
        if idx == -1:
            idx = referer.find(sep, len("https://"))
        if idx != -1:
            return referer[:idx]
    return referer


def is_allowed_origin(request: Request, settings: Settings) -> bool:
    origin = _origin_from_request(request)
    if origin is None:
        return False
    return origin in _origin_urls(settings)


def apply_security_headers(response: Response) -> None:
    for key, value in SECURITY_HEADERS.items():
        if key not in response.headers:
            response.headers[key] = value


async def csrf_token_from_request(request: Request) -> str | None:
    header = request.headers.get("X-CSRF-Token")
    if header:
        return header.strip()
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data") or content_type.startswith(
        "application/x-www-form-urlencoded"
    ):
        form = await request.form()
        field = form.get("csrf_token")
        if field is not None:
            return str(field)
    return None


def csrf_tokens_match(expected: str, provided: str | None) -> bool:
    if not provided:
        return False
    return hmac.compare_digest(provided, expected)


async def validate_mutation(request: Request) -> None:
    """Raise HTTPException 403 when Origin or CSRF validation fails."""
    from fastapi import HTTPException

    settings: Settings = request.app.state.settings
    if not is_allowed_origin(request, settings):
        raise HTTPException(status_code=403, detail="Forbidden")
    expected: str = request.app.state.csrf_token
    provided = await csrf_token_from_request(request)
    if not csrf_tokens_match(expected, provided):
        raise HTTPException(status_code=403, detail="Forbidden")


class HostAndHeadersMiddleware(BaseHTTPMiddleware):
    """Reject disallowed Host values; attach security headers to every response."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if not is_allowed_host(request.headers.get("host")):
            return JSONResponse({"detail": "Invalid Host"}, status_code=400)
        response = await call_next(request)
        apply_security_headers(response)
        return response
