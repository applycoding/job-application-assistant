import httpx2
import pytest

from tests.adapters.contract_helpers import (
    VALID_DRAFT_JSON,
    assert_missing_api_key,
    make_provider,
    outbound_draft,
    run_contract_suite,
    run_model_override,
    success_handler,
)

PROVIDER = "openai"


@pytest.mark.adapters
@pytest.mark.asyncio
async def test_openai_contract() -> None:
    await run_contract_suite(PROVIDER)


@pytest.mark.adapters
def test_openai_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    assert_missing_api_key(PROVIDER, monkeypatch)


@pytest.mark.adapters
@pytest.mark.asyncio
async def test_openai_model_override() -> None:
    await run_model_override(PROVIDER)


@pytest.mark.adapters
@pytest.mark.asyncio
async def test_openai_incomplete_response() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200,
            json={
                "id": "r",
                "object": "response",
                "created_at": 1,
                "status": "incomplete",
                "model": "m",
                "output": [],
            },
        )

    provider = make_provider(PROVIDER, handler)
    with pytest.raises(ValueError, match="incomplete"):
        await provider.draft(outbound_draft())
    await provider.aclose()


@pytest.mark.adapters
@pytest.mark.asyncio
async def test_openai_refusal_content() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200,
            json={
                "id": "r",
                "object": "response",
                "created_at": 1,
                "status": "completed",
                "model": "m",
                "output": [
                    {
                        "id": "o",
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "refusal", "refusal": "no"}],
                    }
                ],
            },
        )

    provider = make_provider(PROVIDER, handler)
    with pytest.raises(ValueError, match="refusal"):
        await provider.draft(outbound_draft())
    await provider.aclose()


@pytest.mark.adapters
@pytest.mark.asyncio
async def test_openai_store_false() -> None:
    captured: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured.append(request)
        return success_handler(PROVIDER, VALID_DRAFT_JSON)(request)

    provider = make_provider(PROVIDER, handler)
    await provider.draft(outbound_draft())
    from tests.adapters.contract_helpers import request_json

    assert request_json(captured[0])["store"] is False
    await provider.aclose()
