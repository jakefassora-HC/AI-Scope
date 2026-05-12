"""Tests for scope.git_scanner — uses real tmp git repos."""
import subprocess
from pathlib import Path
import pytest
from scope.git_scanner import scan_repo, find_repos


def _run(args, cwd):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """A bare-bones git repo with one commit and one dirty file."""
    repo = tmp_path / "myrepo"
    repo.mkdir()
    _run(["git", "init", "-b", "main"], cwd=repo)
    _run(["git", "config", "user.email", "t@t.t"], cwd=repo)
    _run(["git", "config", "user.name", "t"], cwd=repo)
    (repo / "a.txt").write_text("hi")
    _run(["git", "add", "a.txt"], cwd=repo)
    _run(["git", "commit", "-m", "initial"], cwd=repo)
    (repo / "b.txt").write_text("dirty")  # untracked
    return repo


def test_scan_repo_reports_branch(tmp_repo: Path):
    r = scan_repo(tmp_repo)
    assert r["branch"] == "main"


def test_scan_repo_reports_untracked(tmp_repo: Path):
    r = scan_repo(tmp_repo)
    assert r["untracked"] == 1


def test_scan_repo_reports_clean_zero_dirty(tmp_repo: Path):
    r = scan_repo(tmp_repo)
    assert r["dirty"] == 0


def test_scan_repo_returns_last_commit_iso(tmp_repo: Path):
    r = scan_repo(tmp_repo)
    assert "T" in r["last_commit_iso"]


def test_find_repos_locates_subdir_repo(tmp_path: Path, tmp_repo: Path):
    # tmp_repo is at tmp_path/myrepo; find_repos at tmp_path should find it.
    found = find_repos(tmp_path)
    paths = [r["path"] for r in found]
    assert str(tmp_repo) in paths
