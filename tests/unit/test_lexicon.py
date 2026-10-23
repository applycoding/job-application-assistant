from jaa.truth.lexicon import SkillLexicon


def test_find_python():
    lex = SkillLexicon.load(None)
    assert "Python" in lex.find("I use Python daily")
