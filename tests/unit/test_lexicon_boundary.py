"""Skill lexicon token boundaries at sentence end."""

from jaa.truth.lexicon import SkillLexicon


def test_skill_before_sentence_period() -> None:
    lex = SkillLexicon.load(None)
    assert "Kubernetes" in lex.find("I have production experience with Kubernetes.")
    assert "Python" in lex.find("Built services in Python.")
    assert "AWS" in lex.find("I am certified in AWS.")
    assert "Apache Spark" in lex.find("We use Spark;")


def test_dot_net_matches() -> None:
    lex = SkillLexicon.load(None)
    assert ".NET" in lex.find("Shipped services on .NET 8.")


def test_node_dot_js_still_matches() -> None:
    lex = SkillLexicon.load(None)
    found = lex.find("Experience with Node.js in production.")
    assert "Node.js" in found or any("node" in s.lower() for s in found)
