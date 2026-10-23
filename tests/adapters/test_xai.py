import httpx2
import pytest

from tests.adapters.contract_helpers import (
    PROVIDER_URLS,
    VALID_DRAFT_JSON,
    assert_missing_api_key,
    make_provider,
    outbound_draft,
    request_json,
    run_contract_suite,
    run_model_override,
    success_handler,
)

PROVIDER = "xai"


@pytest.mark.adapters
@pytest.mark.asyncio
async def test_xai_contract() -> None:
    await run_contract_suite(PROVIDER)


@pytest.mark.adapters
def test_xai_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    assert_missing_api_key(PROVIDER, monkeypatch)


@pytest.mark.adapters
@pytest.mark.asyncio
async def test_xai_model_override() -> None:
    await run_model_override(PROVIDER)


@pytest.mark.adapters
@pytest.mark.asyncio
async def test_xai_responses_url_and_store() -> None:
    captured: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured.append(request)
        return success_handler(PROVIDER, VALID_DRAFT_JSON)(request)

    provider = make_provider(PROVIDER, handler)
    await provider.draft(outbound_draft())
    assert str(captured[0].url) == PROVIDER_URLS["xai"]
    assert request_json(captured[0])["store"] is False
    await provider.aclose()
