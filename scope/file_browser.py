"""On-demand directory listing.

Single-level (not recursive). Refuses paths outside HOME or matching
the deny list. Symlinks not followed.
"""
from __future__ import annotations
import os
from pathlib import Path
from datetime import datetime

from scope.exclusions import is_excluded


def _ensure_under_home(path: Path) -> None:
    home = Path.home().resolve()
    resolved = path.resolve()
    if home not in resolved.parents and resolved != home:
        raise PermissionError(f"path outside home: {path}")


def list_dir(path: Path) -> list[dict]:
    """Return one dict per immediate child of `path`. Single level only."""
    _ensure_under_home(path)
    if is_excluded(path):
        raise PermissionError(f"excluded path: {path}")
    if not path.exists() or not path.is_dir():
        return []

    items: list[dict] = []
    try:
        entries = list(os.scandir(path))
    except (PermissionError, OSError):
        return []

    for entry in entries:
        p = Path(entry.path)
        if is_excluded(p):
            continue
        try:
            stat = entry.stat(follow_symlinks=False)
        except OSError:
            continue
        items.append({
            "name": entry.name,
            "path": str(p),
            "is_dir": entry.is_dir(follow_symlinks=False),
            "size_bytes": stat.st_size if entry.is_file(follow_symlinks=False) else 0,
            "modified_iso": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        })
    items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
    return items
