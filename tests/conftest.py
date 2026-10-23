"""Global pytest fixtures: socket guard, env scrub, app client, deterministic ids."""

from __future__ import annotations

import os
import socket
from collections.abc import Generator
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from jaa.app import create_app
from jaa.clock import FixedClock
from jaa.config import Settings
from jaa.ids import SeqIdFactory
from jaa.storage.repo import Repository
from jaa.truth.lexicon import SkillLexicon
from tests.support.csrf_client import CsrfClient

REFERENCE_DATE = date(2026, 10, 23)
FIXED_NOW = datetime(2026, 10, 23, 9, 0, 0, tzinfo=UTC)

# Captured before autouse fixtures replace HOME (Playwright browser cache location).
PLAYWRIGHT_BROWSERS_PATH = os.environ.get(
    "PLAYWRIGHT_BROWSERS_PATH",
    str(Path.home() / ".cache" / "ms-playwright"),
)

_LOOPBACK = frozenset({"127.0.0.1", "::1", "localhost"})


def _is_loopback_address(host: object) -> bool:
    if host is None:
        return True
    if isinstance(host, tuple) and host:
        host = host[0]
    if isinstance(host, bytes):
        host = host.decode("ascii", errors="ignore")
    text = str(host).strip().lower()
    if text in _LOOPBACK:
        return True
    return bool(text.startswith("127."))


_original_connect = socket.socket.connect
_original_connect_ex = socket.socket.connect_ex
_original_getaddrinfo = socket.getaddrinfo
_connect_attempts: list[tuple[object, object]] = []


def _guarded_connect(self: socket.socket, address: object) -> None:
    host = address[0] if isinstance(address, tuple) and address else address
    if not _is_loopback_address(host):
        _connect_attempts.append((host, address))
        raise OSError(f"network blocked by test socket guard: {host!r}")
    return _original_connect(self, address)


def _guarded_connect_ex(self: socket.socket, address: object) -> int:
    host = address[0] if isinstance(address, tuple) and address else address
    if not _is_loopback_address(host):
        _connect_attempts.append((host, address))
        return 111
    return _original_connect_ex(self, address)


def _guarded_getaddrinfo(*args: object, **kwargs: object) -> list[tuple]:
    host = args[0] if args else kwargs.get("host")
    if host and not _is_loopback_address(host):
        _connect_attempts.append((host, args))
        raise OSError(f"getaddrinfo blocked by test socket guard: {host!r}")
    return _original_getaddrinfo(*args, **kwargs)


@pytest.fixture(scope="session", autouse=True)
def _socket_guard_session() -> Generator[None]:
    with (
        patch("socket.socket.connect", _guarded_connect),
        patch("socket.socket.connect_ex", _guarded_connect_ex),
        patch("socket.getaddrinfo", _guarded_getaddrinfo),
    ):
        yield


@pytest.fixture(autouse=True)
def _socket_guard_reset() -> None:
    _connect_attempts.clear()


@pytest.fixture
def socket_connect_attempts() -> list[tuple[object, object]]:
    return _connect_attempts


def test_socket_guard_blocks_non_loopback() -> None:
    import pytest as pt

    with pt.raises(OSError, match="network blocked"):
        s = socket.socket()
        try:
            s.connect(("203.0.113.1", 80))
        finally:
            s.close()


@pytest.fixture(autouse=True)
def _env_scrub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("JAA_PROVIDER", "mock")
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    for key in list(os.environ):
        if key.endswith("_API_KEY") or key.endswith("_BASE_URL"):
            monkeypatch.delenv(key, raising=False)
        if key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    return tmp_path / "test.sqlite3"


@pytest.fixture
def fixed_clock() -> FixedClock:
    return FixedClock(FIXED_NOW)


@pytest.fixture
def seq_ids() -> SeqIdFactory:
    return SeqIdFactory(1)


@pytest.fixture
def settings(tmp_db: Path) -> Settings:
    return Settings(
        provider="mock",
        db_path=tmp_db,
        samples_dir=Path("samples"),
        enable_samples=True,
        host="127.0.0.1",
        port=8000,
        reference_date=REFERENCE_DATE,
        run_deadline_s=120.0,
    )


def _wire_test_app(app, settings: Settings, clock: FixedClock, ids: SeqIdFactory) -> None:
    lexicon: SkillLexicon = app.state.lexicon
    engine = app.state.engine
    app.state.settings = settings
    app.state.clock = clock
    app.state.ids = ids
    app.state.repo = Repository(engine, clock, ids, lexicon)


@pytest.fixture
def app(settings: Settings, fixed_clock: FixedClock, seq_ids: SeqIdFactory):
    application = create_app(settings)
    _wire_test_app(application, settings, fixed_clock, seq_ids)
    return application


@pytest.fixture
def raw_client(app) -> TestClient:
    return TestClient(app, base_url="http://127.0.0.1:8000")


@pytest.fixture
def client(app, raw_client: TestClient) -> CsrfClient:
    token = app.state.csrf_token
    return CsrfClient(raw_client, origin="http://127.0.0.1:8000", csrf_token=token)


@pytest.fixture
def repo(app) -> Repository:
    return app.state.repo
