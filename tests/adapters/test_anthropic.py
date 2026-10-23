import json

import httpx2
import pytest

from tests.adapters.contract_helpers import (
    make_provider,
    outbound_draft,
    request_json,
    run_contract_suite,
    success_handler,
    assert_missing_api_key,
    run_model_override,
    VALID_DRAFT_JSON,
)

PROVIDER = "anthropic"


@pytest.mark.adapters
@pytest.mark.asyncio
async def test_anthropic_contract() -> None:
    await run_contract_suite(PROVIDER)


@pytest.mark.adapters
def test_anthropic_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    assert_missing_api_key(PROVIDER, monkeypatch)


@pytest.mark.adapters
@pytest.mark.asyncio
async def test_anthropic_model_override() -> None:
    await run_model_override(PROVIDER)


@pytest.mark.adapters
@pytest.mark.asyncio
async def test_anthropic_stop_reason_not_end_turn() -> None:
    captured: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured.append(request)
        body = json.loads(VALID_DRAFT_JSON)
        return httpx2.Response(
            200,
            json={
                "id": "m",
                "type": "message",
                "role": "assistant",
                "content": [{"type": "text", "text": json.dumps(body)}],
                "model": "x",
                "stop_reason": "max_tokens",
                "stop_sequence": None,
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    provider = make_provider(PROVIDER, handler)
    with pytest.raises(ValueError, match="stop_reason"):
        await provider.draft(outbound_draft())
    assert len(captured) == 1
    await provider.aclose()


@pytest.mark.adapters
@pytest.mark.asyncio
async def test_anthropic_refusal_no_text_block() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200,
            json={
                "id": "m",
                "type": "message",
                "role": "assistant",
                "content": [],
                "model": "x",
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    provider = make_provider(PROVIDER, handler)
    with pytest.raises(ValueError, match="No text block"):
        await provider.draft(outbound_draft())
    await provider.aclose()


@pytest.mark.adapters
@pytest.mark.asyncio
async def test_anthropic_messages_shape() -> None:
    captured: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured.append(request)
        return success_handler(PROVIDER, VALID_DRAFT_JSON)(request)

    provider = make_provider(PROVIDER, handler)
    await provider.draft(outbound_draft())
    body = request_json(captured[0])
    assert body["messages"] == [
        {
            "role": "user",
            "content": [{"type": "text", "text": body["messages"][0]["content"][0]["text"]}],
        }
    ]
    assert "output_config" in body
    await provider.aclose()
