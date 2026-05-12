"""Per-repo git status — uses GitPython.

For each repo: branch, dirty/untracked counts, ahead/behind, stash count,
worktree count, last commit ISO, staleness flag.
"""
from __future__ import annotations
import os
from pathlib import Path
from datetime import datetime, timezone

from git import Repo, InvalidGitRepositoryError, NoSuchPathError

from scope.exclusions import is_excluded


def _ahead_behind(repo: Repo) -> tuple[int, int]:
    try:
        branch = repo.active_branch
        tracking = branch.tracking_branch()
        if tracking is None:
            return (0, 0)
        ahead = sum(1 for _ in repo.iter_commits(f"{tracking}..{branch}"))
        behind = sum(1 for _ in repo.iter_commits(f"{branch}..{tracking}"))
        return ahead, behind
    except Exception:
        return (0, 0)


def scan_repo(path: Path) -> dict:
    """Scan a single git repo at `path`. Raises if not a repo."""
    repo = Repo(path)
    head = repo.head
    branch_name = head.ref.name if not head.is_detached else "(detached)"

    dirty = len([item for item in repo.index.diff(None)])  # modified, not staged
    staged = len([item for item in repo.index.diff("HEAD")]) if not head.is_detached else 0
    untracked = len(repo.untracked_files)
    ahead, behind = _ahead_behind(repo)

    try:
        stash_count = len(repo.git.stash("list").splitlines()) if repo.git.stash("list") else 0
    except Exception:
        stash_count = 0

    try:
        worktree_count = len(repo.git.worktree("list").splitlines())
    except Exception:
        worktree_count = 1

    last_commit = head.commit
    last_commit_dt = datetime.fromtimestamp(last_commit.committed_date, tz=timezone.utc)
    age_days = (datetime.now(tz=timezone.utc) - last_commit_dt).days

    return {
        "path": str(path),
        "branch": branch_name,
        "dirty": dirty + staged,
        "untracked": untracked,
        "ahead": ahead,
        "behind": behind,
        "stash_count": stash_count,
        "worktree_count": worktree_count,
        "last_commit_iso": last_commit_dt.isoformat(timespec="seconds"),
        "age_days": age_days,
        "stale": age_days > 14 and (dirty + staged + untracked) > 0,
    }


def find_repos(root: Path) -> list[dict]:
    """Find git repos in immediate children of `root` and scan each."""
    if not root.exists():
        return []
    results: list[dict] = []
    for entry in os.scandir(root):
        if not entry.is_dir(follow_symlinks=False):
            continue
        p = Path(entry.path)
        if is_excluded(p):
            continue
        try:
            results.append(scan_repo(p))
        except (InvalidGitRepositoryError, NoSuchPathError):
            continue
        except Exception:
            continue
    return results
