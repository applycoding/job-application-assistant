def test_redact_in_outbound():
    from jaa.privacy.redact import redact

    assert "secret" not in redact("email secret@x.com")
