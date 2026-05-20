"""Per-phase git signals.

For each `.planning/phases/<phase>/` directory, compute lightweight git
signals that drive the v2.6 3-status taxonomy (done / active / idle):

  - last_commit_at:        unix ts of latest commit touching the phase dir
  - commit_count:          commits that touched files inside the phase dir
  - referenced_in_commits: commits whose message references the phase name
                           (the actual implementation work outside .planning)
  - merged_to_main:        best-effort detection of a matching branch
                           name (feat/<phase>, feature/<phase>, etc.) that
                           is reachable from main / master

Results are memoized by (repo_path, HEAD_sha, phase_name) so repeat calls
during the same git HEAD are free.
"""
from __future__ import annotations
import re
import subprocess
import time
from typing import Optional

_CACHE: dict[tuple[str, str, str], dict] = {}
_REPO_CTX_CACHE: dict[tuple[str, str], dict] = {}  # (repo_path, sha) -> {merged_branches}


def _run(cwd: str, args: list[str], timeout: float = 2.0) -> str:
    """Run a git command; return stdout text or '' on any failure."""
    try:
        r = subprocess.run(
            ["git", "-C", cwd, *args],
            capture_output=True, text=True, timeout=timeout, check=False,
        )
        if r.returncode != 0:
            return ""
        return r.stdout
    except (subprocess.TimeoutExpired, OSError):
        return ""


def _head_sha(repo_path: str) -> str:
    return _run(repo_path, ["rev-parse", "HEAD"]).strip()


def _merged_branches(repo_path: str) -> list[str]:
    """Return branch names merged into main/master. Empty if neither exists."""
    base = None
    for candidate in ("main", "master"):
        if _run(repo_path, ["show-ref", "--verify", "--quiet", f"refs/heads/{candidate}"]):
            base = candidate
            break
        # show-ref with --quiet has no stdout; check by trying rev-parse instead
        if _run(repo_path, ["rev-parse", "--verify", f"refs/heads/{candidate}"]).strip():
            base = candidate
            break
    if not base:
        return []
    out = _run(repo_path, ["branch", "--merged", base, "--format=%(refname:short)"])
    return [b.strip() for b in out.splitlines() if b.strip()]


def _repo_ctx(repo_path: str, sha: str) -> dict:
    key = (repo_path, sha)
    if key in _REPO_CTX_CACHE:
        return _REPO_CTX_CACHE[key]
    ctx = {"merged_branches": {b.lower() for b in _merged_branches(repo_path)}}
    _REPO_CTX_CACHE[key] = ctx
    return ctx


def phase_git_signals(repo_path: str, phase_dir: str, phase_name: str,
                      sha: Optional[str] = None) -> dict:
    """Compute git signals for one phase directory.

    Args:
      repo_path: absolute path to the repo root.
      phase_dir: absolute path to the phase directory.
      phase_name: e.g. "06-dedup-scoring-replies".
      sha: optional pre-fetched HEAD sha (saves a subprocess).

    Returns: dict with keys last_commit_at, commit_count, referenced_in_commits,
             merged_to_main. Missing values default to 0 / False.
    """
    if sha is None:
        sha = _head_sha(repo_path)
    if not sha:
        return _empty()

    key = (repo_path, sha, phase_name)
    if key in _CACHE:
        return _CACHE[key]

    rel = _relpath(phase_dir, repo_path)
    if rel is None:
        result = _empty()
        _CACHE[key] = result
        return result

    log_out = _run(repo_path, ["log", "--format=%ct", "--", rel])
    commit_timestamps = [int(x) for x in log_out.split() if x.isdigit()]
    commit_count = len(commit_timestamps)
    last_commit_at = max(commit_timestamps) if commit_timestamps else 0

    pattern = _safe_phase_pattern(phase_name)
    ref_out = _run(repo_path, [
        "log", "--format=%H", "-i", "--extended-regexp", f"--grep={pattern}",
    ])
    referenced_in_commits = len([h for h in ref_out.split() if h])

    ctx = _repo_ctx(repo_path, sha)
    merged_lc = ctx["merged_branches"]
    branch_candidates = {
        f"feat/{phase_name}", f"feature/{phase_name}",
        f"phase/{phase_name}", phase_name,
    }
    num = re.match(r"^(\d+)", phase_name)
    if num:
        for prefix in ("feat", "feature", "phase"):
            branch_candidates.add(f"{prefix}/{num.group(1)}")
    merged_to_main = any(b.lower() in merged_lc for b in branch_candidates)

    result = {
        "last_commit_at": last_commit_at,
        "commit_count": commit_count,
        "referenced_in_commits": referenced_in_commits,
        "merged_to_main": merged_to_main,
    }
    _CACHE[key] = result
    return result


def phase_git_signals_batch(repo_path: str, phases: list[dict]) -> list[dict]:
    """Compute signals for many phases in parallel.

    `phases` is a list of {"path": ..., "name": ...}. Returns a parallel list
    of the signal dicts in the same order. Uses a small thread pool; git
    subprocess is I/O bound so threads scale linearly.
    """
    from concurrent.futures import ThreadPoolExecutor

    sha = _head_sha(repo_path)
    if not sha or not phases:
        return [_empty() for _ in phases]

    # Warm the repo context cache before fanning out
    _repo_ctx(repo_path, sha)

    def _one(p: dict) -> dict:
        return phase_git_signals(repo_path, p["path"], p["name"], sha=sha)

    with ThreadPoolExecutor(max_workers=8) as pool:
        return list(pool.map(_one, phases))


def _empty() -> dict:
    return {
        "last_commit_at": 0,
        "commit_count": 0,
        "referenced_in_commits": 0,
        "merged_to_main": False,
    }


def _relpath(phase_dir: str, repo_path: str) -> Optional[str]:
    if not phase_dir.startswith(repo_path):
        return None
    rel = phase_dir[len(repo_path):].lstrip("/")
    return rel or None


def _safe_phase_pattern(phase_name: str) -> str:
    """Escape phase name for grep -E and require word-boundary-ish anchoring.

    A phase name like "01-auth" otherwise matches "author"; require it to be
    surrounded by non-letter chars on both sides.
    """
    escaped = re.escape(phase_name)
    return f"(^|[^a-zA-Z]){escaped}([^a-zA-Z]|$)"


def now_ts() -> int:
    return int(time.time())
