"""Provider that mimics StructuredLLMProvider retry then 502 on invalid drafts."""

from __future__ import annotations

from jaa.models import JudgeOut, LLMDraftOut
from jaa.privacy.outbound import OutboundDraft, OutboundJudge
from jaa.providers.base import CallBudget, ProviderError
from jaa.providers.validate import DraftInvariantError, validate_draft


class InvalidDraftTwiceProvider:
    name = "scripted"
    model = "invalid-twice"
    judge_model = "invalid-twice-judge"

    def __init__(self, *, draft: LLMDraftOut, budget: CallBudget | None = None) -> None:
        self._draft = draft
        self._budget = budget or CallBudget()
        self.draft_calls = 0
        self.judge_calls = 0

    async def draft(self, req: OutboundDraft) -> LLMDraftOut:
        for _ in range(2):
            self._budget.charge()
            self.draft_calls += 1
            try:
                validate_draft(self._draft, req)
                return self._draft
            except DraftInvariantError:
                continue
        raise ProviderError("The model returned invalid output after retry")

    async def judge(self, req: OutboundJudge) -> JudgeOut:
        self.judge_calls += 1
        raise ProviderError("judge not configured")
