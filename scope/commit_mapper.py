"""Map git commits to planning phases.

For a repo + phase, returns the commits attributed to that phase. A commit
is attributed if either:

  (a) it touched any file inside `.planning/phases/<phase>/`, OR
  (b) its commit message matches the phase name (word-boundary-anchored
      so "01-auth" does not match "author").

Output is sorted newest-first. Each commit carries sha, date, subject,
author short-name, file count, and a list of touched files (capped).

Results are memoized by (repo, HEAD-sha, phase) — same pattern as
git_phase_scanner.
"""
from __future__ import annotations
import re
import subprocess
from typing import Optional

_CACHE: dict[tuple[str, str, str], list[dict]] = {}
_MAX_COMMITS = 50
_MAX_FILES_PER_COMMIT = 12
# null-byte field separator inside a record + null-record separator: lets us
# robustly parse `git log` output even when commit messages contain newlines.
_FMT = "%H%x00%ct%x00%an%x00%s"


def _run(cwd: str, args: list[str], timeout: float = 3.0) -> str:
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


def _safe_phase_pattern(phase_name: str) -> str:
    escaped = re.escape(phase_name)
    return f"(^|[^a-zA-Z]){escaped}([^a-zA-Z]|$)"


def _relpath(phase_dir: str, repo_path: str) -> Optional[str]:
    if not phase_dir.startswith(repo_path):
        return None
    rel = phase_dir[len(repo_path):].lstrip("/")
    return rel or None


def _parse_log(out: str) -> dict[str, dict]:
    """Parse `git log -z --format=…` output into {sha: {meta}}."""
    by_sha: dict[str, dict] = {}
    for record in out.split("\x00\x00"):
        if not record.strip():
            continue
        parts = record.split("\x00")
        if len(parts) < 4:
            continue
        sha, ts, author, subject = parts[0], parts[1], parts[2], parts[3]
        if not sha or not ts.isdigit():
            continue
        by_sha[sha] = {
            "sha": sha,
            "short": sha[:7],
            "ts": int(ts),
            "author": author,
            "subject": subject.strip(),
        }
    return by_sha


def _commit_files(repo_path: str, sha: str) -> list[str]:
    out = _run(repo_path, ["show", "--name-only", "--format=", sha])
    files = [ln for ln in out.split("\n") if ln.strip()]
    return files[:_MAX_FILES_PER_COMMIT]


def phase_commits(repo_path: str, phase_dir: str, phase_name: str) -> list[dict]:
    """Return commits attributed to a phase, newest first."""
    sha = _head_sha(repo_path)
    if not sha:
        return []

    key = (repo_path, sha, phase_name)
    if key in _CACHE:
        return _CACHE[key]

    rel = _relpath(phase_dir, repo_path)

    # Source A: commits that touched the phase dir itself
    by_sha: dict[str, dict] = {}
    if rel:
        out = _run(repo_path, [
            "log", "-z", f"--format={_FMT}%x00%x00", "--no-merges",
            "-n", str(_MAX_COMMITS), "--", rel,
        ])
        by_sha.update(_parse_log(out))

    # Source B: commit messages that reference the phase name
    pattern = _safe_phase_pattern(phase_name)
    out = _run(repo_path, [
        "log", "-z", f"--format={_FMT}%x00%x00", "--no-merges",
        "-n", str(_MAX_COMMITS),
        "-i", "--extended-regexp", f"--grep={pattern}",
    ])
    for sha_b, meta in _parse_log(out).items():
        if sha_b not in by_sha:
            by_sha[sha_b] = meta

    # Hydrate files for each commit (bounded, so this stays cheap)
    commits = list(by_sha.values())
    commits.sort(key=lambda c: c["ts"], reverse=True)
    commits = commits[:_MAX_COMMITS]
    for c in commits:
        c["files"] = _commit_files(repo_path, c["sha"])

    _CACHE[key] = commits
    return commits


def invalidate_cache() -> None:
    """Force-clear the memoization (used by tests)."""
    _CACHE.clear()
