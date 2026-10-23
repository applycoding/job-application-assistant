"""OpenAI and xAI Responses structured output adapters."""

from __future__ import annotations

from typing import Any

from jaa.config import Settings
from jaa.providers.base import StructuredLLMProvider

try:
    import httpx2
    from openai import AsyncOpenAI
except ImportError:  # pragma: no cover
    httpx2 = None  # type: ignore[assignment]
    AsyncOpenAI = None  # type: ignore[misc, assignment]


class OpenAIProvider(StructuredLLMProvider):
    name = "openai"

    def __init__(
        self,
        settings: Settings,
        api_key: str,
        model: str,
        judge_model: str,
        *,
        base_url: str | None = None,
        store: bool = False,
        transport: Any | None = None,
        budget: Any | None = None,
    ) -> None:
        super().__init__(budget=budget)
        if AsyncOpenAI is None or httpx2 is None:
            msg = "Install the llm extra: uv sync --extra llm"
            raise ImportError(msg)
        self.model = model
        self.judge_model = judge_model
        self._store = store
        http_client = httpx2.AsyncClient(transport=transport) if transport else httpx2.AsyncClient()
        kwargs: dict[str, Any] = {
            "api_key": api_key,
            "http_client": http_client,
            "max_retries": 2,
            "timeout": settings.request_timeout_s,
        }
        if base_url:
            kwargs["base_url"] = base_url
        self._client = AsyncOpenAI(**kwargs)

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
        response = await self._client.responses.create(
            model=model,
            instructions=system,
            input=[{"role": "user", "content": user}],
            text={
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "schema": schema,
                    "strict": True,
                }
            },
            store=self._store,
            max_output_tokens=4096,
        )
        if response.status == "incomplete":
            raise ValueError("incomplete response")
        for item in response.output or []:
            if item.type == "message":
                for part in item.content or []:
                    if part.type == "refusal":
                        raise ValueError("refusal")
                    if part.type == "output_text":
                        return part.text
        raise ValueError("No output_text in response")


class XAIProvider(OpenAIProvider):
    name = "xai"

    def __init__(
        self,
        settings: Settings,
        api_key: str,
        model: str,
        judge_model: str,
        *,
        base_url: str = "https://api.x.ai/v1",
        transport: Any | None = None,
        budget: Any | None = None,
    ) -> None:
        super().__init__(
            settings,
            api_key,
            model,
            judge_model,
            base_url=base_url,
            store=False,
            transport=transport,
            budget=budget,
        )
