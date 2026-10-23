"""Settings parsing tests."""

from datetime import date
from pathlib import Path

import pytest

from jaa.config import Settings


def test_defaults() -> None:
    s = Settings()
    assert s.provider == "mock"
    assert s.judge is False


def test_from_env_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("JAA_PORT=9000\n", encoding="utf-8")
    monkeypatch.delenv("JAA_PORT", raising=False)
    s = Settings.from_env(env={}, dotenv=env_file)
    assert s.port == 9000
    monkeypatch.setenv("JAA_PORT", "8001")
    s2 = Settings.from_env(dotenv=env_file)
    assert s2.port == 8001


def test_invalid_provider_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JAA_PROVIDER", "not-a-provider")
    with pytest.raises(ValueError, match="Unknown JAA_PROVIDER"):
        Settings.from_env()


def test_reference_date_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JAA_REFERENCE_DATE", "2026-10-23")
    s = Settings.from_env()
    assert s.reference_date == date(2026, 10, 23)
