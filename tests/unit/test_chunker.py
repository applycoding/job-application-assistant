from jaa.ingest.chunker import chunk_document
from jaa.models import RawLine


def test_chunk_ids_stable_within_section():
    lines = [RawLine(line_no=1, text="Alpha", kind="bullet", section=["A"])]
    c1 = chunk_document("doc1", lines)
    c2 = chunk_document("doc1", lines)
    assert [c.id for c in c1] == [c.id for c in c2]


def test_chunk_ids_stable_across_doc_id():
    lines = [RawLine(line_no=1, text="Alpha", kind="bullet", section=["A"])]
    sha = "a" * 64
    c1 = chunk_document("doc-a", lines, content_sha256=sha)
    c2 = chunk_document("doc-b", lines, content_sha256=sha)
    assert [c.id for c in c1] == [c.id for c in c2]
    assert ":" not in c1[0].id
