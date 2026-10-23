from jaa.jobs.requirements import requirement_terms


def test_terms_prefers_skills():
    terms = requirement_terms("Strong Python experience", ["Python"])
    assert terms == ["Python"]
