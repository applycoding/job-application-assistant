"""Google Gemini structured JSON output adapter."""

from __future__ import annotations

from typing import Any

from jaa.config import Settings
from jaa.providers.base import StructuredLLMProvider

try:
    from google import genai
    from google.genai import types
except ImportError:  # pragma: no cover
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]


class GoogleProvider(StructuredLLMProvider):
    name = "google"

    def __init__(
        self,
        settings: Settings,
        api_key: str,
        model: str,
        judge_model: str,
        *,
        http_options: Any | None = None,
        budget: Any | None = None,
    ) -> None:
        super().__init__(budget=budget)
        if genai is None or types is None:
            msg = "Install the llm extra: uv sync --extra llm"
            raise ImportError(msg)
        self.model = model
        self.judge_model = judge_model
        opts = http_options or types.HttpOptions(
            timeout=int(settings.request_timeout_s * 1000),
        )
        self._client = genai.Client(api_key=api_key, http_options=opts)

    async def aclose(self) -> None:
        await self._client.aio.aclose()

    async def _complete_json(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema: dict[str, Any],
        schema_name: str,
    ) -> str:
        response = await self._client.aio.models.generate_content(
            model=model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_json_schema=schema,
                max_output_tokens=4096,
            ),
        )
        if response.prompt_feedback and response.prompt_feedback.block_reason:
            raise ValueError(f"blocked: {response.prompt_feedback.block_reason}")
        if not response.candidates:
            raise ValueError("empty candidates")
        candidate = response.candidates[0]
        if candidate.finish_reason and str(candidate.finish_reason) != "STOP":
            raise ValueError(f"finish_reason: {candidate.finish_reason}")
        text = response.text
        if not text:
            raise ValueError("empty text")
        return text
