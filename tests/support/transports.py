"""Fail-closed httpx / httpx2 mock transports for adapter tests."""

from __future__ import annotations

from typing import Any

import httpx


class UnexpectedRequest(RuntimeError):
    """Raised when no handler matched a mock transport request."""


def httpx_handler(handler: Any) -> httpx.MockTransport:
    """Wrap a handler so unmatched requests raise UnexpectedRequest."""

    def wrapped(request: httpx.Request) -> httpx.Response:
        response = handler(request)
        if response is None:
            raise UnexpectedRequest(f"Unmatched request: {request.method} {request.url}")
        return response

    return httpx.MockTransport(wrapped)


def httpx2_handler(handler: Any) -> Any:
    """Build httpx2.MockTransport with fail-closed semantics."""
    import httpx2

    def wrapped(request: httpx2.Request) -> httpx2.Response:
        response = handler(request)
        if response is None:
            raise UnexpectedRequest(f"Unmatched request: {request.method} {request.url}")
        return response

    return httpx2.MockTransport(wrapped)
