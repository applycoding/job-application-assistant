from jaa.models import Chunk, Requirement
from jaa.retrieval.eligibility import eligible
from jaa.truth.lexicon import SkillLexicon


def test_eligibility_requires_term() -> None:
    chunks = [Chunk(id="c1", doc_id="d", line_no=1, kind="bullet", text="Python only", section="S")]
    req = Requirement(id="R1", text="Go required", priority="must", skills=["Go"], terms=["go"])
    lex = SkillLexicon.load(None)
    assert eligible(chunks[0], req, lex) == []
