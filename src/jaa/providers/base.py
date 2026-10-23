"""LLM provider protocol, structured base class, and call budget."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, Protocol

from pydantic import ValidationError

from jaa.limits import MAX_PROVIDER_CALLS_PER_RUN
from jaa.models import JudgeOut, LLMDraftOut
from jaa.privacy.outbound import OutboundDraft, OutboundJudge
from jaa.providers.prompts import (
    DRAFT_SYSTEM,
    JUDGE_SYSTEM,
    append_validation_error,
    build_user_message,
)
from jaa.providers.schema import portable_json_schema
from jaa.providers.validate import DraftInvariantError, validate_draft, validate_judge


class ProviderError(RuntimeError):
    """User-facing provider failure; run is not saved."""


class ProviderConfigError(RuntimeError):
    """Startup configuration error."""


class JudgeUnavailable(RuntimeError):
    """Judge call failed; claims should become not_verified."""


class CallBudget:
    def __init__(self, limit: int = MAX_PROVIDER_CALLS_PER_RUN) -> None:
        self._limit = limit
        self._used = 0

    def charge(self) -> None:
        self._used += 1
        if self._used > self._limit:
            raise ProviderError("Too many provider calls for this run")

    @property
    def used(self) -> int:
        return self._used


class LLMProvider(Protocol):
    name: str
    model: str
    judge_model: str

    async def draft(self, req: OutboundDraft) -> LLMDraftOut: ...

    async def judge(self, req: OutboundJudge) -> JudgeOut: ...


class StructuredLLMProvider(ABC):
    name: str
    model: str
    judge_model: str

    def __init__(self, *, budget: CallBudget | None = None) -> None:
        self._budget = budget or CallBudget()

    @abstractmethod
    async def _complete_json(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema: dict[str, Any],
        schema_name: str,
    ) -> str: ...

    async def draft(self, req: OutboundDraft) -> LLMDraftOut:
        schema = portable_json_schema(LLMDraftOut)
        user = build_user_message(req, judge=False)
        last_error: str | None = None
        for attempt in range(2):
            self._budget.charge()
            msg = append_validation_error(user, last_error) if last_error else user
            try:
                raw = await self._complete_json(
                    model=self.model,
                    system=DRAFT_SYSTEM,
                    user=msg,
                    schema=schema,
                    schema_name="draft",
                )
                data = json.loads(raw)
                out = LLMDraftOut.model_validate(data)
                validate_draft(out, req)
                return out
            except (json.JSONDecodeError, ValidationError, DraftInvariantError) as exc:
                last_error = str(exc)
        raise ProviderError("The model returned invalid output after retry")

    async def judge(self, req: OutboundJudge) -> JudgeOut:
        if not req.items:
            return JudgeOut(verdicts=[])
        schema = portable_json_schema(JudgeOut)
        user = build_user_message(req, judge=True)
        last_error: str | None = None
        for attempt in range(2):
            self._budget.charge()
            msg = append_validation_error(user, last_error) if last_error else user
            try:
                raw = await self._complete_json(
                    model=self.judge_model,
                    system=JUDGE_SYSTEM,
                    user=msg,
                    schema=schema,
                    schema_name="judge",
                )
                data = json.loads(raw)
                out = JudgeOut.model_validate(data)
                validate_judge(out, req)
                return out
            except (json.JSONDecodeError, ValidationError, DraftInvariantError) as exc:
                last_error = str(exc)
        raise JudgeUnavailable("Judge returned invalid output after retry")
