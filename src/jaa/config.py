"""Application settings from environment and optional ``.env`` file."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, field_validator

ProviderName = Literal["mock", "anthropic", "openai", "google", "xai"]

_BUILTIN_PROVIDERS = Path(__file__).resolve().parent / "resources" / "providers.toml"


def _parse_dotenv(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        out[key] = value
    return out


def _coalesce(env: Mapping[str, str], key: str, dotenv: Mapping[str, str]) -> str | None:
    if key in env:
        return env[key]
    return dotenv.get(key)


class Settings(BaseModel):
    provider: ProviderName = "mock"
    model: str | None = None
    judge_model: str | None = None
    judge: bool = False
    db_path: Path = Path("var/jaa.sqlite3")
    samples_dir: Path = Path("samples")
    enable_samples: bool = True
    host: str = "127.0.0.1"
    port: int = 8000
    public_port: int | None = None
    reference_date: date | None = None
    skills_file: Path | None = None
    max_upload_mb: int = 5
    request_timeout_s: float = 60.0
    run_deadline_s: float = 120.0
    instance_nonce: str | None = None

    @field_validator("db_path", "samples_dir", "skills_file", mode="before")
    @classmethod
    def _path_from_str(cls, v: object) -> object:
        if v is None or isinstance(v, Path):
            return v
        if isinstance(v, str):
            return Path(v)
        return v

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        dotenv: Path | None = Path(".env"),
    ) -> Self:
        import os

        raw_env = dict(env) if env is not None else dict(os.environ)
        file_vars = _parse_dotenv(dotenv) if dotenv is not None else {}

        def get(key: str) -> str | None:
            return _coalesce(raw_env, key, file_vars)

        provider_raw = get("JAA_PROVIDER")
        if provider_raw is not None and provider_raw not in (
            "mock",
            "anthropic",
            "openai",
            "google",
            "xai",
        ):
            allowed = "mock, anthropic, openai, google, xai"
            raise ValueError(f"Unknown JAA_PROVIDER '{provider_raw}'; allowed: {allowed}")

        judge_raw = get("JAA_JUDGE")
        judge = False
        if judge_raw is not None:
            judge = judge_raw.strip().lower() in ("on", "true", "1", "yes")

        ref_raw = get("JAA_REFERENCE_DATE")
        reference_date: date | None = None
        if ref_raw:
            reference_date = date.fromisoformat(ref_raw)

        public_port_raw = get("JAA_PUBLIC_PORT")
        public_port: int | None = None
        if public_port_raw:
            public_port = int(public_port_raw)

        skills_raw = get("JAA_SKILLS_FILE")
        skills_file = Path(skills_raw) if skills_raw else None

        enable_samples_raw = get("JAA_ENABLE_SAMPLES")
        enable_samples = True
        if enable_samples_raw is not None:
            enable_samples = enable_samples_raw.strip().lower() not in ("0", "false", "off", "no")

        data: dict[str, object] = {
            "provider": provider_raw or "mock",
            "model": get("JAA_MODEL"),
            "judge_model": get("JAA_JUDGE_MODEL"),
            "judge": judge,
            "db_path": get("JAA_DB_PATH") or "var/jaa.sqlite3",
            "samples_dir": get("JAA_SAMPLES_DIR") or "samples",
            "enable_samples": enable_samples,
            "host": get("JAA_HOST") or "127.0.0.1",
            "port": int(get("JAA_PORT") or "8000"),
            "public_port": public_port,
            "reference_date": reference_date,
            "skills_file": skills_file,
            "max_upload_mb": int(get("JAA_MAX_UPLOAD_MB") or "5"),
            "request_timeout_s": float(get("JAA_REQUEST_TIMEOUT_S") or "60.0"),
            "run_deadline_s": float(get("JAA_RUN_DEADLINE_S") or "120.0"),
            "instance_nonce": get("JAA_INSTANCE_NONCE"),
        }
        return cls.model_validate(data)

    def resolved_reference_date(self, clock_date: date | None = None) -> date:
        if self.reference_date is not None:
            return self.reference_date
        if clock_date is not None:
            return clock_date
        return date.today()

    def resolved_models(self) -> tuple[str, str]:
        with _BUILTIN_PROVIDERS.open("rb") as f:
            providers = tomllib.load(f)
        section = providers.get(self.provider)
        if section is None:
            raise ValueError(f"Provider '{self.provider}' not found in providers.toml")
        model = self.model or str(section["model"])
        judge_model = self.judge_model or str(section["judge_model"])
        return model, judge_model

    def resolved_public_port(self) -> int:
        return self.public_port if self.public_port is not None else self.port
