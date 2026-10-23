"""Anthropic structured JSON output adapter."""

from __future__ import annotations

from typing import Any

from jaa.config import Settings
from jaa.providers.base import StructuredLLMProvider

try:
    import httpx2
    from anthropic import AsyncAnthropic
except ImportError:  # pragma: no cover - optional llm extra
    httpx2 = None  # type: ignore[assignment]
    AsyncAnthropic = None  # type: ignore[misc, assignment]


class AnthropicProvider(StructuredLLMProvider):
    name = "anthropic"

    def __init__(
        self,
        settings: Settings,
        api_key: str,
        model: str,
        judge_model: str,
        *,
        transport: Any | None = None,
        budget: Any | None = None,
    ) -> None:
        super().__init__(budget=budget)
        if AsyncAnthropic is None or httpx2 is None:
            msg = "Install the llm extra: uv sync --extra llm"
            raise ImportError(msg)
        self.model = model
        self.judge_model = judge_model
        http_client = httpx2.AsyncClient(transport=transport) if transport else httpx2.AsyncClient()
        self._client = AsyncAnthropic(
            api_key=api_key,
            http_client=http_client,
            max_retries=2,
            timeout=settings.request_timeout_s,
        )

    async def aclose(self) -> None:
        await self._client.close()

    async def _complete_json(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema: dict[str, Any],
        schema_name: str,
    ) -> str:
        response = await self._client.messages.create(
            model=model,
            max_tokens=4096,
            system=system,
            messages=[
                {
                    "role": "user",
                    "content": [{"type": "text", "text": user}],
                }
            ],
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": schema,
                }
            },
        )
        if response.stop_reason != "end_turn":
            msg = f"Unexpected stop_reason: {response.stop_reason}"
            raise ValueError(msg)
        for block in response.content:
            if block.type == "text":
                return block.text
        raise ValueError("No text block in response")
