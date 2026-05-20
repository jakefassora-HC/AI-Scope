"""Find running `claude` Code CLI processes.

Reads only cmdline / cwd / create_time / open file paths via psutil.
Open files are filtered to plan documents (.md / .html / .htm) so we
can show which planning document a Claude is actively working on.
Never reads file contents of other processes' open handles.
"""
from __future__ import annotations
import time
import psutil

PLAN_EXTS = (".md", ".html", ".htm")


def _open_plan_files(proc: psutil.Process) -> list[str]:
    """Return absolute paths of plan files currently open by `proc`.

    Returns [] on any permission/lookup error — never raises.
    """
    try:
        files = proc.open_files()
    except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
        return []
    out: list[str] = []
    for f in files:
        path = getattr(f, "path", "")
        if not path:
            continue
        lower = path.lower()
        if lower.endswith(PLAN_EXTS):
            out.append(path)
    return out


def find_claude_processes() -> list[dict]:
    """Return dicts for each running process whose name == 'claude'."""
    results: list[dict] = []
    for proc in psutil.process_iter(["pid", "name", "cmdline", "cwd", "create_time"]):
        try:
            info = proc.info
            if info.get("name") != "claude":
                continue
            open_plans = _open_plan_files(proc)
            results.append({
                "pid": info["pid"],
                "cmdline": " ".join(info.get("cmdline") or []),
                "cwd": info.get("cwd") or "",
                "uptime_sec": int(time.time() - info.get("create_time", time.time())),
                "open_plans": open_plans,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, KeyError):
            continue
    return results
