import pytest

from jaa.config import Settings
from jaa.providers.base import ProviderError
from jaa.providers.registry import build_provider
from tests.support.transports import httpx2_handler


@pytest.mark.adapters
@pytest.mark.asyncio
async def test_unmatched_request(socket_connect_attempts):
    settings = Settings(provider="openai")
    import os

    os.environ["OPENAI_API_KEY"] = "test-key"
    transport = httpx2_handler(lambda req: None)
    provider = build_provider(settings, transport=transport)
    from jaa.models import Question
    from jaa.privacy.outbound import OutboundDraft, OutboundEvidence

    req = OutboundDraft(
        job_title="t",
        company=None,
        requirements=[],
        questions=[Question(id="Q1", text="q")],
        evidence=[OutboundEvidence(id="c1", section="s", text="t")],
        gap_terms=[],
    )
    with pytest.raises(ProviderError):
        await provider.draft(req)
    assert socket_connect_attempts == []
