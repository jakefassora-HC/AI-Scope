"""Tests for scope.rules — deterministic insight rules."""
from scope.rules import evaluate_all, Severity


def _file(size_bytes=1000, age_days=1, path="/Users/j/projects/foo/CLAUDE.md", auto=True):
    return {
        "path": path,
        "size_bytes": size_bytes,
        "tokens_est": size_bytes // 4,
        "age_days": age_days,
        "auto_loaded": auto,
    }


def _repo(dirty=0, untracked=0, ahead=0, age_days=1, path="/Users/j/projects/foo"):
    return {
        "path": path, "branch": "main", "dirty": dirty, "untracked": untracked,
        "ahead": ahead, "behind": 0, "stash_count": 0, "worktree_count": 1,
        "age_days": age_days, "stale": False,
    }


def test_auto_loaded_and_large_triggers_high():
    findings = evaluate_all(
        config_files=[_file(size_bytes=20000, auto=True)],
        repos=[],
        worktrees=[],
        home_is_git_repo=False,
    )
    assert any(f["rule"] == "auto_loaded_and_large" and f["severity"] == Severity.HIGH
               for f in findings)


def test_stale_auto_loaded_triggers_med():
    findings = evaluate_all(
        config_files=[_file(age_days=60, auto=True)],
        repos=[], worktrees=[], home_is_git_repo=False,
    )
    assert any(f["rule"] == "stale_auto_loaded" for f in findings)


def test_home_is_git_repo_triggers_high():
    findings = evaluate_all(config_files=[], repos=[], worktrees=[], home_is_git_repo=True)
    assert any(f["rule"] == "home_is_git_repo" and f["severity"] == Severity.HIGH
               for f in findings)


def test_orphaned_worktree_triggers_med():
    wt = _repo(age_days=60)
    findings = evaluate_all(config_files=[], repos=[], worktrees=[wt],
                            home_is_git_repo=False)
    assert any(f["rule"] == "orphaned_worktree" for f in findings)


def test_dirty_unpushed_stale_triggers_med():
    r = _repo(dirty=2, ahead=3, age_days=14)
    findings = evaluate_all(config_files=[], repos=[r], worktrees=[],
                            home_is_git_repo=False)
    assert any(f["rule"] == "dirty_unpushed_stale" for f in findings)


def test_clean_state_no_findings():
    findings = evaluate_all(config_files=[], repos=[], worktrees=[],
                            home_is_git_repo=False)
    assert findings == []
