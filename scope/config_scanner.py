"""Walks ~/.claude/ and locates CLAUDE.md files across the user's home.

Returns dicts with path, size, estimated tokens, last modified.
All paths gated by `scope.exclusions.is_excluded`.
"""
from __future__ import annotations
import os
from pathlib import Path
from datetime import datetime

from scope.exclusions import is_excluded
from scope.token_estimator import estimate_tokens_from_bytes

# Files Claude Code actually injects into every turn's context. Plugin
# caches, session transcripts, tool-result blobs, and lockfiles live under
# ~/.claude/ but never auto-load — flagging them as "loads every turn" was
# false signal that drowned the real findings.
AUTO_LOADED_ROOT_FILES: frozenset[str] = frozenset({
    "CLAUDE.md",
    "settings.json",
    "settings.local.json",
})
AUTO_LOADED_SUBDIRS: frozenset[str] = frozenset({"rules"})


def _describe(path: Path, auto_loaded: bool = True) -> dict:
    from datetime import timezone
    stat = path.stat()
    mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
    return {
        "path": str(path),
        "name": path.name,
        "size_bytes": stat.st_size,
        "tokens_est": estimate_tokens_from_bytes(stat.st_size),
        "modified_iso": mtime.isoformat(timespec="seconds"),
        "age_days": (datetime.now(tz=timezone.utc) - mtime).days,
        "auto_loaded": auto_loaded,
    }


def scan_claude_dir(claude_dir: Path) -> list[dict]:
    """Return dicts for files Claude Code auto-loads from `claude_dir`.

    Scope is narrow on purpose: only top-level config + rules/*.md. The wider
    `.claude/` tree (plugin caches, session transcripts, tool-results, etc.) is
    NOT auto-loaded and is excluded so the insights panel stays honest.
    """
    if not claude_dir.exists():
        return []
    results: list[dict] = []

    for fname in AUTO_LOADED_ROOT_FILES:
        p = claude_dir / fname
        if not p.is_file() or is_excluded(p):
            continue
        try:
            results.append(_describe(p))
        except (OSError, PermissionError):
            continue

    for subdir_name in AUTO_LOADED_SUBDIRS:
        subdir = claude_dir / subdir_name
        if not subdir.is_dir() or is_excluded(subdir):
            continue
        try:
            entries = list(os.scandir(subdir))
        except (OSError, PermissionError):
            continue
        for entry in entries:
            if not entry.is_file(follow_symlinks=False):
                continue
            if not entry.name.endswith(".md"):
                continue
            p = Path(entry.path)
            if is_excluded(p):
                continue
            try:
                results.append(_describe(p))
            except (OSError, PermissionError):
                continue

    return results


def find_claude_md_files(root: Path) -> list[dict]:
    """Find every `CLAUDE.md` under `root` (recursively), respecting deny list."""
    if not root.exists():
        return []
    results: list[dict] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if not is_excluded(Path(dirpath) / d)]
        for fname in filenames:
            if fname != "CLAUDE.md":
                continue
            p = Path(dirpath) / fname
            if is_excluded(p):
                continue
            try:
                results.append(_describe(p))
            except (OSError, PermissionError):
                continue
    return results
