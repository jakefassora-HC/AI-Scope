"""Planning directory scanner.

Surfaces:
  * milestone/phase state (parses GSD STATE.md frontmatter)
  * the actual plan documents — markdown and html — that live inside
    planning-like folders (.planning, plans, planning, docs) or at repo root
    (CLAUDE.md, README.md, ROADMAP.md, etc).

Pure I/O over filesystem; no network. Tolerant of missing files.
"""
from __future__ import annotations
import re
from datetime import datetime, timezone
from os import scandir
from pathlib import Path
from typing import Optional

from scope.token_estimator import estimate_tokens_from_bytes

PLAN_EXTS = (".md", ".html", ".htm")
PLANNING_DIRS = (".planning", "plans", "planning", "docs", ".gsd")
ROOT_PLAN_FILES = (
    "CLAUDE.md", "README.md", "ROADMAP.md", "PROJECT.md",
    "REQUIREMENTS.md", "BRIEF.md", "STATE.md", "AGENTS.md",
)
MAX_WALK_DEPTH = 4
PHASE_DIR_RE = re.compile(r"\.planning/phases/([^/]+)/")


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


def _file_record(path: Path, rel: str, phase: Optional[str] = None,
                 phase_status: Optional[str] = None) -> dict:
    stat = path.stat()
    mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
    return {
        "path": str(path),
        "name": path.name,
        "rel": rel,
        "ext": path.suffix.lower().lstrip("."),
        "size_bytes": stat.st_size,
        "tokens_est": estimate_tokens_from_bytes(stat.st_size),
        "age_days": (datetime.now(tz=timezone.utc) - mtime).days,
        "phase": phase,
        "phase_status": phase_status,
    }


def _walk_plans(base: Path, repo_root: Path, depth: int = 0) -> list[dict]:
    """Recursively collect *.md / *.html files under `base`."""
    if depth > MAX_WALK_DEPTH:
        return []
    out: list[dict] = []
    try:
        entries = list(scandir(base))
    except (OSError, PermissionError):
        return out
    for entry in entries:
        if entry.name.startswith("."):
            # allow `.planning` itself (entered via initial call) but skip nested dotdirs
            if depth > 0:
                continue
        try:
            if entry.is_dir(follow_symlinks=False):
                out.extend(_walk_plans(Path(entry.path), repo_root, depth + 1))
            elif entry.is_file(follow_symlinks=False) and entry.name.lower().endswith(PLAN_EXTS):
                p = Path(entry.path)
                rel = str(p.relative_to(repo_root))
                m = PHASE_DIR_RE.search(rel + "/")
                phase = m.group(1) if m else None
                phase_status = None
                if phase:
                    phase_status = _phase_status(repo_root / ".planning" / "phases" / phase)
                out.append(_file_record(p, rel, phase=phase, phase_status=phase_status))
        except (OSError, PermissionError):
            continue
    return out


def list_plan_files(repo_path: str) -> list[dict]:
    """Return every plan document (md/html) discoverable in a repo.

    Coverage:
      * top-level ROOT_PLAN_FILES (CLAUDE.md, README.md, ROADMAP.md, …)
      * recursive walk of `.planning/`, `plans/`, `planning/`, `docs/`, `.gsd/`
        (capped depth to keep scans fast on large doc trees)

    Each record carries a `phase` (e.g. "06-dedup-scoring-replies") and
    `phase_status` when the file lives under `.planning/phases/<phase>/`.
    """
    root = Path(repo_path)
    if not root.is_dir():
        return []
    seen: set[str] = set()
    out: list[dict] = []

    # Top-level well-known docs
    for name in ROOT_PLAN_FILES:
        p = root / name
        if p.is_file():
            rec = _file_record(p, name)
            seen.add(rec["path"])
            out.append(rec)

    # Recursive walks of planning-like dirs
    for d in PLANNING_DIRS:
        sub = root / d
        if sub.is_dir():
            for rec in _walk_plans(sub, root):
                if rec["path"] in seen:
                    continue
                seen.add(rec["path"])
                out.append(rec)

    return out
