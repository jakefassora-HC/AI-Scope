"""Tests for git_phase_scanner — uses tmp git repos."""
from __future__ import annotations
import subprocess
from pathlib import Path

import pytest

from scope.git_phase_scanner import phase_git_signals, _CACHE, _REPO_CTX_CACHE


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _CACHE.clear()
    _REPO_CTX_CACHE.clear()
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@t.test")
    _git(tmp_path, "config", "user.name", "tester")
    (tmp_path / ".planning" / "phases" / "01-foo").mkdir(parents=True)
    (tmp_path / ".planning" / "phases" / "01-foo" / "01-PLAN.md").write_text("plan")
    return tmp_path


def test_phase_with_no_commits_yet(repo: Path):
    s = phase_git_signals(
        str(repo),
        str(repo / ".planning/phases/01-foo"),
        "01-foo",
    )
    assert s["commit_count"] == 0
    assert s["last_commit_at"] == 0


def test_phase_commits_counted(repo: Path):
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add 01-foo plan")
    s = phase_git_signals(
        str(repo),
        str(repo / ".planning/phases/01-foo"),
        "01-foo",
    )
    assert s["commit_count"] == 1
    assert s["last_commit_at"] > 0
    # referenced in commit message
    assert s["referenced_in_commits"] >= 1


def test_referenced_commit_outside_phase_dir(repo: Path):
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")
    (repo / "code.py").write_text("# 01-foo implementation")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "feat(01-foo): implement scaffolding")
    s = phase_git_signals(
        str(repo),
        str(repo / ".planning/phases/01-foo"),
        "01-foo",
    )
    # 1 commit touched .planning/phases/01-foo, 1 commit message references "01-foo"
    assert s["commit_count"] == 1
    assert s["referenced_in_commits"] == 1


def test_merged_branch_detected(repo: Path):
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")
    _git(repo, "checkout", "-b", "feat/01-foo")
    (repo / "x.txt").write_text("x")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "feat work")
    _git(repo, "checkout", "main")
    _git(repo, "merge", "--no-ff", "feat/01-foo", "-m", "merge")
    _CACHE.clear()
    _REPO_CTX_CACHE.clear()
    s = phase_git_signals(
        str(repo),
        str(repo / ".planning/phases/01-foo"),
        "01-foo",
    )
    assert s["merged_to_main"] is True


def test_cache_hit_is_fast(repo: Path):
    import time as _t
    _git(repo, "add", "."); _git(repo, "commit", "-m", "x")
    t0 = _t.perf_counter()
    phase_git_signals(str(repo), str(repo / ".planning/phases/01-foo"), "01-foo")
    cold = _t.perf_counter() - t0
    t1 = _t.perf_counter()
    phase_git_signals(str(repo), str(repo / ".planning/phases/01-foo"), "01-foo")
    warm = _t.perf_counter() - t1
    # Cache hit should be meaningfully faster than cold path
    assert warm < cold / 3
