from jaa.ids import SeqIdFactory


def test_seq_ids():
    f = SeqIdFactory(1)
    assert f.new_doc_id().endswith("000000000001")
