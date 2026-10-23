from jaa.privacy.redact import redact


def test_redact_email():
    assert "[email]" in redact("Contact me@secret.com today")
