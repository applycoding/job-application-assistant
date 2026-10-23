import pytest

from jaa.providers.base import CallBudget, ProviderError


def test_call_budget_max_four() -> None:
    budget = CallBudget()
    for _ in range(4):
        budget.charge()
    with pytest.raises(ProviderError, match="Too many provider"):
        budget.charge()
