"""GSD .planning/ directory scanner.

Surfaces milestone state and phase status for the Map treemap. Pure I/O over
filesystem; no network. Tolerant of missing/malformed files — returns None
when a repo has no usable planning data.
"""
from __future__ import annotations
from os import scandir
from pathlib import Path
from typing import Optional


def _parse_yaml_frontmatter(text: str) -> dict:
    """Minimal YAML frontmatter parser — flat scalars + one-level nested keys.

    We avoid pulling PyYAML for one file. Only handles the shapes GSD emits.
    """
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    body = text[3:end].strip("\n")
    out: dict = {}
    current_key: Optional[str] = None
    current_indent = 0
    for raw in body.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        line = raw.strip()
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if indent == 0:
            if v == "":
                out[k] = {}
                current_key = k
                current_indent = indent
            else:
                out[k] = _coerce(v)
                current_key = None
        elif current_key and indent > current_indent:
            if isinstance(out.get(current_key), dict):
                out[current_key][k] = _coerce(v)
    return out


def _coerce(v: str):
    if v in ("true", "false"):
        return v == "true"
    try:
        if "." in v:
            return float(v)
        return int(v)
    except ValueError:
        return v


def _phase_status(phase_dir: Path) -> str:
    """Classify a phase directory.

    - 'complete': has a *-VERIFICATION.md file
    - 'iterating': has any *-PLAN.md but no VERIFICATION
    - 'planning': has DISCUSS.md or RESEARCH.md only
    - 'draft': else
    """
    try:
        names = [e.name for e in scandir(phase_dir) if e.is_file(follow_symlinks=False)]
    except (OSError, PermissionError):
        return "draft"
    if any(n.endswith("-VERIFICATION.md") or n == "VERIFICATION.md" for n in names):
        return "complete"
    if any(n.endswith("-PLAN.md") or n == "PLAN.md" for n in names):
        return "iterating"
    if any(n in ("DISCUSS.md", "RESEARCH.md") for n in names):
        return "planning"
    return "draft"


def scan_planning(repo_path: str) -> Optional[dict]:
    """Return planning summary for a repo, or None if no .planning/ dir.

    Shape:
      {
        "milestone": str,
        "status": str,        # e.g. "executing", "complete"
        "percent": int,       # 0..100
        "total_phases": int,
        "completed_phases": int,
        "phases": [{"name": str, "status": str, "path": str}, ...],
      }
    """
    planning = Path(repo_path) / ".planning"
    if not planning.is_dir():
        return None

    state_file = planning / "STATE.md"
    frontmatter: dict = {}
    if state_file.is_file():
        try:
            frontmatter = _parse_yaml_frontmatter(state_file.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            frontmatter = {}

    progress = frontmatter.get("progress", {}) if isinstance(frontmatter.get("progress"), dict) else {}

    phases_dir = planning / "phases"
    phases: list[dict] = []
    if phases_dir.is_dir():
        try:
            entries = sorted(
                (e for e in scandir(phases_dir) if e.is_dir(follow_symlinks=False)),
                key=lambda e: e.name,
            )
        except (OSError, PermissionError):
            entries = []
        for entry in entries:
            phases.append({
                "name": entry.name,
                "status": _phase_status(Path(entry.path)),
                "path": entry.path,
            })

    total = progress.get("total_phases") if isinstance(progress.get("total_phases"), int) else len(phases)
    completed = progress.get("completed_phases") if isinstance(progress.get("completed_phases"), int) else sum(
        1 for p in phases if p["status"] == "complete"
    )
    percent = progress.get("percent") if isinstance(progress.get("percent"), int) else (
        int(round(100 * completed / total)) if total else 0
    )

    return {
        "milestone": frontmatter.get("milestone", ""),
        "milestone_name": frontmatter.get("milestone_name", ""),
        "status": frontmatter.get("status", ""),
        "percent": percent,
        "total_phases": total,
        "completed_phases": completed,
        "phases": phases,
    }
