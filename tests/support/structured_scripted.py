"""StructuredLLMProvider test double with scripted JSON completions."""

from __future__ import annotations

from typing import Any

from jaa.providers.base import StructuredLLMProvider


class ScriptedStructuredProvider(StructuredLLMProvider):
    """Returns fixed JSON strings from _complete_json (uses real draft() retry logic)."""

    name = "scripted-structured"
    model = "scripted-structured-1"
    judge_model = "scripted-structured-judge-1"

    def __init__(self, *, draft_json: str) -> None:
        super().__init__()
        self._draft_json = draft_json
        self.complete_calls = 0

    async def _complete_json(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema: dict[str, Any],
        schema_name: str,
    ) -> str:
        self.complete_calls += 1
        return self._draft_json
