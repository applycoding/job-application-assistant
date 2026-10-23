import pytest


@pytest.mark.adapters
def test_skip():
    pytest.importorskip("openai")
