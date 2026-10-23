"""Injectable time source for deterministic tests."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FixedClock:
    def __init__(self, fixed: datetime) -> None:
        if fixed.tzinfo is None:
            fixed = fixed.replace(tzinfo=timezone.utc)
        self._fixed = fixed

    def now(self) -> datetime:
        return self._fixed
