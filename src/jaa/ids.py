"""Document id generation."""

from __future__ import annotations

import uuid
from typing import Protocol


class IdFactory(Protocol):
    def new_doc_id(self) -> str: ...


class Uuid4Factory:
    def new_doc_id(self) -> str:
        return str(uuid.uuid4())


class SeqIdFactory:
    """Deterministic uuid-shaped ids for tests."""

    def __init__(self, start: int = 1) -> None:
        self._next = start

    def new_doc_id(self) -> str:
        n = self._next
        self._next += 1
        return f"00000000-0000-4000-8000-{n:012x}"
