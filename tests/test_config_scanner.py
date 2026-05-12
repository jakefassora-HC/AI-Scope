"""Tests for scope.config_scanner."""
from pathlib import Path
from scope.config_scanner import scan_claude_dir, find_claude_md_files


def test_scan_claude_dir_returns_files(fake_home: Path):
    results = scan_claude_dir(fake_home / ".claude")
    paths = [r["path"] for r in results]
    assert str(fake_home / ".claude" / "CLAUDE.md") in paths
    assert str(fake_home / ".claude" / "settings.json") in paths


def test_scan_claude_dir_excludes_session_transcripts(fake_home: Path):
    results = scan_claude_dir(fake_home / ".claude")
    paths = [r["path"] for r in results]
    assert not any("projects/session.jsonl" in p for p in paths)


def test_scan_claude_dir_includes_size_and_tokens(fake_home: Path):
    results = scan_claude_dir(fake_home / ".claude")
    for r in results:
        assert "size_bytes" in r
        assert "tokens_est" in r
        assert r["tokens_est"] >= 0


def test_find_claude_md_files_walks_projects(fake_home: Path):
    results = find_claude_md_files(fake_home / "projects")
    paths = [r["path"] for r in results]
    assert str(fake_home / "projects" / "foo" / "CLAUDE.md") in paths


def test_find_claude_md_skips_ssh_dir(fake_home: Path):
    # Even if a CLAUDE.md somehow exists in .ssh, it must be skipped.
    bad = fake_home / ".ssh" / "CLAUDE.md"
    bad.write_text("# nope")
    results = find_claude_md_files(fake_home)
    paths = [r["path"] for r in results]
    assert str(bad) not in paths
