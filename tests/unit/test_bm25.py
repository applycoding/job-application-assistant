from jaa.models import Chunk
from jaa.retrieval.bm25 import BM25Ranker


def test_bm25_positive_score():
    chunks = [Chunk(id="c1", doc_id="d", line_no=1, kind="bullet", text="python data", section="S")]
    r = BM25Ranker(chunks)
    scores = r.score(["python"], ["c1"])
    assert scores["c1"] > 0
