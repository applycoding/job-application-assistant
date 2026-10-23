from jaa.ingest.classify import classify, keep_line
from jaa.models import RawLine
from jaa.truth.lexicon import SkillLexicon


def test_go_line_kept():
    lex = SkillLexicon.load(None)
    line = RawLine(line_no=1, text="Go", kind="line", section=["Skills"])
    assert keep_line(line, lex)


def test_contact_detection():
    assert classify("Email: a@example.com", md_heading=False, docx_style=None) == "contact"
