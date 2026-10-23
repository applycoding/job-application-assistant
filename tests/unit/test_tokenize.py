from jaa.retrieval.tokenize import tokenize


def test_special_tokens():
    assert "c++" in tokenize("C++ and C# and node.js")
