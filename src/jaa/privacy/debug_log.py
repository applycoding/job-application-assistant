"""Safe debug strings for integration tests and local troubleshooting."""

from __future__ import annotations

from collections.abc import Sequence

from jaa.config import Settings

_REDACTED = "[redacted]"


def scrub_secrets(text: str, secrets: Sequence[str]) -> str:
    out = text
    for secret in secrets:
        if secret:
            out = out.replace(secret, _REDACTED)
    return out


def format_run_debug(settings: Settings, *, job_id: str, chunk_count: int) -> str:
    """Log-friendly run metadata; never includes raw evidence or secret values."""
    standby = settings.log_leak_sentinel or ""
    key_state = "set" if standby else "unset"
    raw = (
        f"create_run job_id={job_id} provider={settings.provider} "
        f"chunks={chunk_count} standby_key={key_state} token={standby}"
    )
    return scrub_secrets(raw, [standby])
