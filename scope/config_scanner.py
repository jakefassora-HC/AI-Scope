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


def _describe(path: Path) -> dict:
    stat = path.stat()
    return {
        "path": str(path),
        "name": path.name,
        "size_bytes": stat.st_size,
        "tokens_est": estimate_tokens_from_bytes(stat.st_size),
        "modified_iso": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
    }


def scan_claude_dir(claude_dir: Path) -> list[dict]:
    """Return one dict per file under `claude_dir`, respecting deny list."""
    if not claude_dir.exists():
        return []
    results: list[dict] = []
    for dirpath, dirnames, filenames in os.walk(claude_dir, followlinks=False):
        # Skip excluded subtrees early
        dirnames[:] = [d for d in dirnames if not is_excluded(Path(dirpath) / d)]
        for fname in filenames:
            p = Path(dirpath) / fname
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
