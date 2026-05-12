"""Fast activity probe — meant to be polled at 1Hz.

Returns:
  - currently-running claude processes (cwd + open plan files)
  - plan files whose mtime is within `recent_window_sec` of now

Designed to take <100ms even on a portfolio with 50+ plans. Stats only,
no subprocess, no recursive walk — caller supplies the list of plan
paths already discovered by the slow /api/treemap scan.
"""
from __future__ import annotations
import os
import time

from scope.process_scanner import find_claude_processes


def scan_activity(plan_paths: list[str], recent_window_sec: int = 60) -> dict:
    """Build an activity snapshot.

    Args:
      plan_paths: absolute paths of every known plan file (md/html). The
          caller (Flask route) keeps this cached from the last /api/treemap
          response. If empty, only process info is returned.
      recent_window_sec: how recently a plan must have been touched to be
          reported in `recent_mtimes`. Default 60 seconds.

    Returns:
      {
        "ts": <unix int>,
        "processes": [{pid, cwd, open_plans}, ...],
        "recent_mtimes": [{path, mtime}, ...]
      }
    """
    now = time.time()
    processes = find_claude_processes()
    # Strip uptime + cmdline — the activity snapshot only needs the bits
    # the map overlay reacts to.
    procs_slim = [{
        "pid": p["pid"],
        "cwd": p.get("cwd", ""),
        "open_plans": p.get("open_plans", []),
    } for p in processes]

    recent: list[dict] = []
    cutoff = now - recent_window_sec
    for path in plan_paths:
        try:
            st = os.stat(path)
        except (OSError, PermissionError):
            continue
        if st.st_mtime >= cutoff:
            recent.append({"path": path, "mtime": int(st.st_mtime)})

    return {
        "ts": int(now),
        "processes": procs_slim,
        "recent_mtimes": recent,
    }
