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


def test_scan_claude_dir_skips_plugin_cache(fake_home: Path):
    # Plugin cache files (and any other deep ~/.claude/ files) are NOT
    # auto-loaded per turn. They must not appear in the scan output.
    cache = fake_home / ".claude" / "plugins" / "cache" / "foo"
    cache.mkdir(parents=True)
    (cache / "schemas.ts").write_text("x" * 50_000)
    (cache / "bun.lock").write_text("y" * 30_000)
    results = scan_claude_dir(fake_home / ".claude")
    paths = [r["path"] for r in results]
    assert not any("plugins/cache" in p for p in paths)


def test_scan_claude_dir_skips_history_and_tool_results(fake_home: Path):
    proj = fake_home / ".claude" / "projects" / "abc"
    proj.mkdir(parents=True)
    (proj / "history.jsonl").write_text("z" * 600_000)
    tr = fake_home / ".claude" / "tool-results"
    tr.mkdir()
    (tr / "blob.txt").write_text("w" * 20_000)
    results = scan_claude_dir(fake_home / ".claude")
    paths = [r["path"] for r in results]
    assert not any("history.jsonl" in p for p in paths)
    assert not any("tool-results" in p for p in paths)


def test_scan_claude_dir_includes_rules_markdown(fake_home: Path):
    rules = fake_home / ".claude" / "rules"
    rules.mkdir()
    (rules / "workflow.md").write_text("# workflow rules\n")
    (rules / "notes.txt").write_text("not a markdown file")
    results = scan_claude_dir(fake_home / ".claude")
    paths = [r["path"] for r in results]
    assert str(rules / "workflow.md") in paths
    assert str(rules / "notes.txt") not in paths
