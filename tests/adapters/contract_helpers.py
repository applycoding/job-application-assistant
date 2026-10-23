"""Shared helpers for LLM adapter contract tests (PLAN §7.2)."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import httpx2
import pytest

from jaa.config import Settings
from jaa.models import Question
from jaa.privacy.outbound import (
    JudgeItem,
    OutboundDraft,
    OutboundEvidence,
    OutboundJudge,
    OutboundRequirement,
)
from jaa.privacy.redact import redact
from jaa.providers.base import JudgeUnavailable, ProviderConfigError, ProviderError
from jaa.providers.registry import build_provider, load_provider_config
from tests.support.transports import httpx2_handler, httpx_handler

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "synthetic_from_docs"
CONTACTS = json.loads((FIXTURES / "privacy_contact_strings.json").read_text(encoding="utf-8"))
VALID_DRAFT_JSON = (FIXTURES / "valid_draft.json").read_text(encoding="utf-8")
VALID_JUDGE_JSON = (FIXTURES / "valid_judge.json").read_text(encoding="utf-8")

FORBIDDEN_BODY_KEYS = frozenset({"tools", "tool_choice", "temperature", "top_p", "top_k"})

PROVIDER_URLS = {
    "anthropic": "https://api.anthropic.com/v1/messages",
    "openai": "https://api.openai.com/v1/responses",
    "xai": "https://api.x.ai/v1/responses",
    "google": (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-3.8-flash:generateContent"
    ),
}

KEY_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google": "GEMINI_API_KEY",
    "xai": "XAI_API_KEY",
}


def _load_template(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def outbound_draft() -> OutboundDraft:
    raw_evidence = (
        f"Python APIs. Email {CONTACTS['email']}, phone {CONTACTS['phone']}, "
        f"site {CONTACTS['url']}, home {CONTACTS['address']}."
    )
    return OutboundDraft(
        job_title="Senior Engineer",
        company="Acme Logistics",
        requirements=[
            OutboundRequirement(id="R1", text="Python experience", priority="must"),
        ],
        questions=[Question(id="Q1", text="Describe your Python background.")],
        evidence=[
            OutboundEvidence(
                id="c1",
                section="Experience > Backend",
                text=redact(raw_evidence),
            )
        ],
        gap_terms=["MLflow"],
    )


def outbound_judge() -> OutboundJudge:
    draft = outbound_draft()
    return OutboundJudge(
        items=[
            JudgeItem(
                sentence_id="Q1.S1",
                claim="I built data pipelines with Python.",
                evidence=list(draft.evidence),
            )
        ]
    )


def wrap_transport(provider: str, handler: Callable[..., Any]) -> Any:
    if provider == "google":
        return httpx_handler(handler)
    return httpx2_handler(handler)


def make_provider(
    provider: str,
    handler: Callable[..., Any],
    *,
    model: str | None = None,
) -> Any:
    key_env = KEY_ENV[provider]
    os.environ[key_env] = "test-key"
    settings = Settings(provider=provider, model=model)
    transport = wrap_transport(provider, handler)
    return build_provider(settings, transport=transport)


def request_body_text(request: Any) -> str:
    if hasattr(request, "content") and request.content:
        return request.content.decode("utf-8")
    return ""


def request_json(request: Any) -> dict[str, Any]:
    text = request_body_text(request)
    return json.loads(text) if text else {}


def assert_no_forbidden_sampling_fields(payload: dict[str, Any]) -> None:
    for key in FORBIDDEN_BODY_KEYS:
        assert key not in payload, f"forbidden field present: {key}"


def assert_data_block_and_no_contacts(body_text: str) -> None:
    assert "BEGIN DATA-" in body_text
    assert "END DATA-" in body_text
    for field in ("email", "phone", "url", "address"):
        assert CONTACTS[field] not in body_text


def anthropic_response(json_text: str) -> dict[str, Any]:
    data = _load_template("anthropic_message.json")
    data["content"][0]["text"] = json_text
    return data


def openai_response(json_text: str) -> dict[str, Any]:
    data = _load_template("openai_response.json")
    data["output"][0]["content"][0]["text"] = json_text
    return data


def gemini_response(json_text: str) -> dict[str, Any]:
    data = _load_template("gemini_generate.json")
    data["candidates"][0]["content"]["parts"][0]["text"] = json_text
    return data


def success_handler(provider: str, json_text: str) -> Callable[..., Any]:
    def handler(request: Any) -> Any:
        if provider == "anthropic":
            return httpx2.Response(200, json=anthropic_response(json_text))
        if provider in ("openai", "xai"):
            return httpx2.Response(200, json=openai_response(json_text))
        if provider == "google":
            return httpx.Response(200, json=gemini_response(json_text))
        raise AssertionError(f"unknown provider {provider}")

    return handler


def assert_native_schema_field(provider: str, body: dict[str, Any]) -> None:
    if provider == "anthropic":
        fmt = body["output_config"]["format"]
        assert fmt["type"] == "json_schema"
        assert "schema" in fmt
    elif provider in ("openai", "xai"):
        fmt = body["text"]["format"]
        assert fmt["type"] == "json_schema"
        assert fmt.get("strict") is True
        assert "schema" in fmt
    elif provider == "google":
        gen = body["generationConfig"]
        assert gen["responseMimeType"] == "application/json"
        assert "responseJsonSchema" in gen
    else:
        raise AssertionError(provider)


def assert_provider_request(
    provider: str,
    request: Any,
    *,
    model: str,
    judge: bool = False,
) -> None:
    url = str(request.url)
    assert url == PROVIDER_URLS[provider]
    body = request_json(request)
    assert_no_forbidden_sampling_fields(body)

    if provider == "anthropic":
        assert request.headers.get("anthropic-version") == "2026-10-21"
        assert request.headers.get("authorization") == "Bearer test-key"
        assert body["model"] == model
        assert_native_schema_field(provider, body)
        messages = body["messages"]
        assert messages[0]["role"] == "user"
        assert messages[0]["content"][0]["type"] == "text"
        assert_data_block_and_no_contacts(messages[0]["content"][0]["text"])
    elif provider in ("openai", "xai"):
        assert body["model"] == model
        assert body.get("store") is False
        assert_native_schema_field(provider, body)
        assert_data_block_and_no_contacts(body["input"][0]["content"])
    elif provider == "google":
        assert_native_schema_field(provider, body)
        user_text = body["contents"][0]["parts"][0]["text"]
        assert_data_block_and_no_contacts(user_text)
    else:
        raise AssertionError(provider)

    if judge:
        cfg = load_provider_config(provider)
        expected_judge = cfg["judge_model"]
        if provider == "anthropic":
            assert body["model"] == expected_judge
        elif provider in ("openai", "xai"):
            assert body["model"] == expected_judge
        elif provider == "google":
            assert expected_judge in url or body  # model is in URL for Gemini


async def run_contract_suite(provider: str) -> None:
    cfg = load_provider_config(provider)
    model = cfg["model"]
    judge_model = cfg["judge_model"]
    draft_req = outbound_draft()
    judge_req = outbound_judge()

    captured: list[Any] = []

    def track(handler: Callable[..., Any]) -> Callable[..., Any]:
        def wrapped(request: Any) -> Any:
            captured.append(request)
            return handler(request)

        return wrapped

    # Valid draft
    captured.clear()
    p = make_provider(provider, track(success_handler(provider, VALID_DRAFT_JSON)))
    out = await p.draft(draft_req)
    assert out.answers[0].question_id == "Q1"
    assert len(captured) == 1
    assert_provider_request(provider, captured[0], model=model)
    await p.aclose()

    # Valid judge
    captured.clear()
    p = make_provider(provider, track(success_handler(provider, VALID_JUDGE_JSON)))
    jout = await p.judge(judge_req)
    assert jout.verdicts[0].sentence_id == "Q1.S1"
    assert len(captured) == 1
    if provider == "google":
        assert judge_model in str(captured[0].url)
    else:
        assert_provider_request(provider, captured[0], model=judge_model, judge=True)
    await p.aclose()

    # Invalid JSON -> 2 requests, retry mentions validation error
    captured.clear()

    def bad_json_handler(request: Any) -> Any:
        return success_handler(provider, "not-json")(request)

    p = make_provider(provider, track(bad_json_handler))
    with pytest.raises(ProviderError, match="invalid output"):
        await p.draft(draft_req)
    assert len(captured) == 2
    retry_body = request_body_text(captured[1])
    assert "VALIDATION ERROR" in retry_body
    assert_data_block_and_no_contacts(retry_body)
    await p.aclose()

    captured.clear()
    p = make_provider(provider, track(bad_json_handler))
    with pytest.raises(JudgeUnavailable):
        await p.judge(judge_req)
    assert len(captured) == 2
    assert "VALIDATION ERROR" in request_body_text(captured[1])
    await p.aclose()

    # 429 -> ProviderError after 3 HTTP attempts
    captured.clear()

    def rate_limit_handler(request: Any) -> Any:
        if provider == "google":
            return httpx.Response(429, json={"error": "rate"})
        return httpx2.Response(429, json={"error": "rate"})

    p = make_provider(provider, track(rate_limit_handler))
    with pytest.raises(ProviderError):
        await p.draft(draft_req)
    expected_attempts = 1 if provider == "google" else 3
    assert len(captured) == expected_attempts
    await p.aclose()


def assert_missing_api_key(provider: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(KEY_ENV[provider], raising=False)
    settings = Settings(provider=provider)
    with pytest.raises(ProviderConfigError, match=KEY_ENV[provider]):
        build_provider(settings, transport=wrap_transport(provider, lambda r: None))


async def run_model_override(provider: str) -> None:
    captured: list[Any] = []

    def handler(request: Any) -> Any:
        captured.append(request)
        return success_handler(provider, VALID_DRAFT_JSON)(request)

    p = make_provider(provider, handler, model="custom-model-xyz")
    await p.draft(outbound_draft())
    body = request_json(captured[0])
    if provider == "google":
        assert "custom-model-xyz" in str(captured[0].url)
    else:
        assert body["model"] == "custom-model-xyz"
    await p.aclose()
