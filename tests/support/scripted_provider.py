"""Test double LLM provider with scripted draft/judge responses."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from jaa.models import JudgeOut, LLMDraftOut
from jaa.privacy.outbound import OutboundDraft, OutboundJudge
from jaa.providers.base import CallBudget, ProviderError
from jaa.providers.validate import validate_draft, validate_judge


class ScriptedProvider:
    name = "scripted"
    model = "scripted-1"
    judge_model = "scripted-judge-1"

    def __init__(
        self,
        *,
        drafts: list[str | LLMDraftOut | dict[str, Any]] | None = None,
        judges: list[str | JudgeOut | dict[str, Any]] | None = None,
        budget: CallBudget | None = None,
        on_draft: Callable[[OutboundDraft], None] | None = None,
        delay_s: float = 0.0,
    ) -> None:
        self._drafts = list(drafts or [])
        self._judges = list(judges or [])
        self._budget = budget or CallBudget()
        self._on_draft = on_draft
        self._delay_s = delay_s
        self.draft_calls = 0
        self.judge_calls = 0

    async def draft(self, req: OutboundDraft) -> LLMDraftOut:
        self._budget.charge()
        self.draft_calls += 1
        if self._on_draft:
            self._on_draft(req)
        if self._delay_s:
            import asyncio

            await asyncio.sleep(self._delay_s)
        if not self._drafts:
            raise ProviderError("no scripted draft")
        raw = self._drafts.pop(0)
        if isinstance(raw, LLMDraftOut):
            out = raw
        elif isinstance(raw, dict):
            out = LLMDraftOut.model_validate(raw)
        else:
            out = LLMDraftOut.model_validate(json.loads(raw))
        validate_draft(out, req)
        return out

    async def judge(self, req: OutboundJudge) -> JudgeOut:
        self._budget.charge()
        self.judge_calls += 1
        if not self._judges:
            raise ProviderError("no scripted judge")
        raw = self._judges.pop(0)
        if isinstance(raw, JudgeOut):
            out = raw
        elif isinstance(raw, dict):
            out = JudgeOut.model_validate(raw)
        else:
            out = JudgeOut.model_validate(json.loads(raw))
        validate_judge(out, req)
        return out
