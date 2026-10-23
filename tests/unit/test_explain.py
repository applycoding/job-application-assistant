from jaa.generation.explain import explain
from jaa.models import Chunk, Requirement, Sentence
from jaa.truth.lexicon import SkillLexicon


def test_explain_terms():
    sent = Sentence(
        id="Q1.S1",
        kind="claim",
        text="Python pipelines",
        citations=["c1"],
        requirement_ids=["R1"],
        rationale="",
    )
    pool = {
        "c1": Chunk(
            id="c1",
            doc_id="d",
            line_no=1,
            kind="bullet",
            text="Built Python pipelines",
            section="S",
        )
    }
    reqs = {
        "R1": Requirement(
            id="R1", text="Python", priority="must", skills=["Python"], terms=["python"]
        )
    }
    exp = explain(sent, reqs, pool, SkillLexicon.load(None))
    assert exp.matches
