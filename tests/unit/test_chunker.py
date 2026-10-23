from jaa.ingest.chunker import chunk_document
from jaa.models import RawLine


def test_chunk_ids_stable_within_section():
    lines = [RawLine(line_no=1, text="Alpha", kind="bullet", section=["A"])]
    c1 = chunk_document("doc1", lines)
    c2 = chunk_document("doc1", lines)
    assert [c.id for c in c1] == [c.id for c in c2]
