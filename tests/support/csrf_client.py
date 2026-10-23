"""TestClient wrapper that adds Origin and CSRF on mutating requests."""

from __future__ import annotations

from typing import Any

from starlette.testclient import TestClient


class CsrfClient:
    def __init__(self, client: TestClient, *, origin: str, csrf_token: str) -> None:
        self._client = client
        self._origin = origin
        self._csrf = csrf_token

    def _headers(self, headers: dict[str, str] | None, *, mutate: bool) -> dict[str, str]:
        out = dict(headers or {})
        if mutate:
            out.setdefault("Origin", self._origin)
            out.setdefault("X-CSRF-Token", self._csrf)
        return out

    def get(self, url: str, **kwargs: Any) -> Any:
        return self._client.get(url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> Any:
        headers = self._headers(kwargs.pop("headers", None), mutate=True)
        return self._client.post(url, headers=headers, **kwargs)

    def put(self, url: str, **kwargs: Any) -> Any:
        headers = self._headers(kwargs.pop("headers", None), mutate=True)
        return self._client.put(url, headers=headers, **kwargs)

    def patch(self, url: str, **kwargs: Any) -> Any:
        headers = self._headers(kwargs.pop("headers", None), mutate=True)
        return self._client.patch(url, headers=headers, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> Any:
        headers = self._headers(kwargs.pop("headers", None), mutate=True)
        return self._client.delete(url, headers=headers, **kwargs)

    @property
    def raw(self) -> TestClient:
        return self._client
