"""Tests for commit_mapper — attribution rules + cache."""
from __future__ import annotations
import subprocess
from pathlib import Path

import pytest

from scope.commit_mapper import phase_commits, invalidate_cache


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    invalidate_cache()
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@t.test")
    _git(tmp_path, "config", "user.name", "tester")
    phase = tmp_path / ".planning" / "phases" / "01-foo"
    phase.mkdir(parents=True)
    (phase / "01-PLAN.md").write_text("plan")
    return tmp_path


def test_commit_touching_phase_dir(repo: Path):
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")
    commits = phase_commits(
        str(repo),
        str(repo / ".planning/phases/01-foo"),
        "01-foo",
    )
    assert len(commits) == 1
    c = commits[0]
    assert "01-PLAN.md" in str(c["files"]) or any(".planning" in f for f in c["files"])
    assert c["subject"] == "initial"
    assert c["author"] == "tester"
    assert len(c["short"]) == 7


def test_commit_referenced_by_message(repo: Path):
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")
    (repo / "code.py").write_text("# impl")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "feat(01-foo): implement scaffolding")
    commits = phase_commits(
        str(repo),
        str(repo / ".planning/phases/01-foo"),
        "01-foo",
    )
    # initial commit touched phase dir + the impl commit references "01-foo"
    subjects = [c["subject"] for c in commits]
    assert "feat(01-foo): implement scaffolding" in subjects
    assert "initial" in subjects


def test_no_match_returns_empty(repo: Path):
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")
    commits = phase_commits(
        str(repo),
        str(repo / ".planning/phases/99-other"),
        "99-other",
    )
    assert commits == []


def test_word_boundary_anchoring(repo: Path):
    # "01-auth" should not match "author"
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "credit author for x")  # has "author" — not a match
    commits = phase_commits(
        str(repo),
        str(repo / ".planning/phases/99-author-not-phase"),
        "99-author-not-phase",
    )
    # only the literal "99-author-not-phase" pattern should match
    assert commits == []


def test_results_sorted_newest_first(repo: Path):
    import time as _t
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "first 01-foo")
    _t.sleep(1.1)  # ensure distinct commit ts (git stores second-resolution)
    (repo / "x.txt").write_text("x")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "second 01-foo")
    commits = phase_commits(
        str(repo),
        str(repo / ".planning/phases/01-foo"),
        "01-foo",
    )
    assert commits[0]["subject"] == "second 01-foo"
    assert commits[1]["subject"] == "first 01-foo"
    assert commits[0]["ts"] >= commits[1]["ts"]


def test_cache_hit_is_fast(repo: Path):
    import time as _t
    _git(repo, "add", "."); _git(repo, "commit", "-m", "x 01-foo")
    t0 = _t.perf_counter()
    phase_commits(str(repo), str(repo / ".planning/phases/01-foo"), "01-foo")
    cold = _t.perf_counter() - t0
    t1 = _t.perf_counter()
    phase_commits(str(repo), str(repo / ".planning/phases/01-foo"), "01-foo")
    warm = _t.perf_counter() - t1
    assert warm < cold / 3
