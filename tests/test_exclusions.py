"""Tests for scope.exclusions — hard deny list."""
from pathlib import Path
import pytest
from scope.exclusions import is_excluded, EXCLUDED_PATTERNS


def test_session_transcripts_dir_excluded():
    assert is_excluded(Path.home() / ".claude" / "projects" / "abc" / "session.jsonl")


def test_credentials_json_excluded():
    assert is_excluded(Path.home() / ".claude" / ".credentials.json")


def test_ssh_dir_excluded():
    assert is_excluded(Path.home() / ".ssh" / "id_rsa")


def test_aws_dir_excluded():
    assert is_excluded(Path.home() / ".aws" / "credentials")


def test_gnupg_dir_excluded():
    assert is_excluded(Path.home() / ".gnupg" / "private-keys-v1.d")


def test_env_file_excluded():
    assert is_excluded(Path("/tmp/.env"))
    assert is_excluded(Path("/tmp/.env.local"))


def test_pem_file_excluded():
    assert is_excluded(Path("/tmp/cert.pem"))


def test_id_rsa_excluded():
    assert is_excluded(Path("/tmp/id_rsa"))
    assert is_excluded(Path("/tmp/id_rsa.pub"))


def test_normal_claude_md_not_excluded():
    assert not is_excluded(Path.home() / "projects" / "foo" / "CLAUDE.md")


def test_normal_settings_json_not_excluded():
    assert not is_excluded(Path.home() / ".claude" / "settings.json")


def test_patterns_constant_is_immutable_tuple():
    assert isinstance(EXCLUDED_PATTERNS, tuple)
