"""Find running `claude` Code CLI processes.

Reads only cmdline / cwd / create_time via psutil. Never reads memory
or open files of other processes.
"""
from __future__ import annotations
import time
import psutil


def find_claude_processes() -> list[dict]:
    """Return dicts for each running process whose name == 'claude'."""
    results: list[dict] = []
    for proc in psutil.process_iter(["pid", "name", "cmdline", "cwd", "create_time"]):
        try:
            info = proc.info
            if info.get("name") != "claude":
                continue
            results.append({
                "pid": info["pid"],
                "cmdline": " ".join(info.get("cmdline") or []),
                "cwd": info.get("cwd") or "",
                "uptime_sec": int(time.time() - info.get("create_time", time.time())),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, KeyError):
            continue
    return results
