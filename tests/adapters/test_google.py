import httpx
import pytest

from tests.adapters.contract_helpers import (
    VALID_DRAFT_JSON,
    assert_missing_api_key,
    make_provider,
    outbound_draft,
    request_json,
    run_contract_suite,
    run_model_override,
    success_handler,
)

PROVIDER = "google"


@pytest.mark.adapters
@pytest.mark.asyncio
async def test_google_contract() -> None:
    await run_contract_suite(PROVIDER)


@pytest.mark.adapters
def test_google_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    assert_missing_api_key(PROVIDER, monkeypatch)


@pytest.mark.adapters
@pytest.mark.asyncio
async def test_google_model_override() -> None:
    await run_model_override(PROVIDER)


@pytest.mark.adapters
@pytest.mark.asyncio
async def test_google_blocked_prompt() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "promptFeedback": {"blockReason": "SAFETY"},
                "candidates": [],
            },
        )

    provider = make_provider(PROVIDER, handler)
    with pytest.raises(ValueError, match="blocked"):
        await provider.draft(outbound_draft())
    await provider.aclose()


@pytest.mark.adapters
@pytest.mark.asyncio
async def test_google_empty_candidates() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"candidates": []})

    provider = make_provider(PROVIDER, handler)
    with pytest.raises(ValueError, match="empty candidates"):
        await provider.draft(outbound_draft())
    await provider.aclose()


@pytest.mark.adapters
@pytest.mark.asyncio
async def test_google_response_json_schema_field() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return success_handler(PROVIDER, VALID_DRAFT_JSON)(request)

    provider = make_provider(PROVIDER, handler)
    await provider.draft(outbound_draft())
    body = request_json(captured[0])
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert "responseJsonSchema" in body["generationConfig"]
    await provider.aclose()
