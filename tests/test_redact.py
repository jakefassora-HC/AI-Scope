"""Tests for scope.redact — regex secret masking."""
from scope.redact import redact


def test_anthropic_api_key_redacted():
    s = "API key: sk-ant-api03-abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    assert "sk-ant-api03" not in redact(s)
    assert "[REDACTED]" in redact(s)


def test_openai_key_redacted():
    s = "OPENAI=sk-proj-AbCdEf1234567890AbCdEf1234567890AbCdEf12"
    assert "sk-proj-AbCdEf" not in redact(s)


def test_github_pat_redacted():
    s = "token=ghp_AbCdEf1234567890AbCdEf1234567890AbCd"
    assert "ghp_" not in redact(s)


def test_aws_access_key_redacted():
    s = "AKIAIOSFODNN7EXAMPLE"
    assert "AKIA" not in redact(s)


def test_slack_bot_token_redacted():
    s = "xoxb-1234567890-1234567890123-AbCdEfGhIjKlMnOpQrStUvWx"
    assert "xoxb-" not in redact(s)


def test_jwt_redacted():
    s = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdef"
    assert "eyJhbGci" not in redact(s)


def test_normal_text_unchanged():
    s = "This is a normal CLAUDE.md file with no secrets."
    assert redact(s) == s


def test_empty_string_safe():
    assert redact("") == ""
