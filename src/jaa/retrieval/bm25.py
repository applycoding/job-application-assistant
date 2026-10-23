from __future__ import annotations

from collections.abc import Sequence

from rank_bm25 import BM25Plus

from jaa.models import Chunk
from jaa.retrieval.tokenize import tokenize


class BM25Ranker:
    def __init__(self, chunks: Sequence[Chunk]) -> None:
        self._chunks = list(chunks)
        self._id_to_index = {c.id: i for i, c in enumerate(self._chunks)}
        corpus = [tokenize(c.evidence_text) for c in self._chunks]
        self._bm25 = BM25Plus(corpus, k1=1.5, b=0.75, delta=1.0)

    def score(self, query: list[str], ids: Sequence[str]) -> dict[str, float]:
        if not query:
            return {cid: 0.0 for cid in ids}
        scores = self._bm25.get_scores(query)
        out: dict[str, float] = {}
        for cid in ids:
            idx = self._id_to_index.get(cid)
            if idx is None:
                out[cid] = 0.0
            else:
                out[cid] = float(scores[idx])
        return out
