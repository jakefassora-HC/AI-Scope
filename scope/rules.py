"""Deterministic insight rules.

Each rule is a pure function over scanner output. Returns a list of
findings; each finding has a rule name, severity, message, and target path.
"""
from __future__ import annotations
from enum import Enum


class Severity(str, Enum):
    LOW = "LOW"
    MED = "MED"
    HIGH = "HIGH"


def _r_auto_loaded_and_large(config_files: list[dict]) -> list[dict]:
    out = []
    for f in config_files:
        if f.get("auto_loaded") and f["size_bytes"] > 8 * 1024:
            out.append({
                "rule": "auto_loaded_and_large",
                "severity": Severity.HIGH,
                "target": f["path"],
                "message": (
                    f"{f['path'].split('/')[-1]} is {f['size_bytes'] // 1024}KB and "
                    f"loads every turn (~{f['tokens_est']:,} tokens). Consider pruning."
                ),
            })
    return out


def _r_stale_auto_loaded(config_files: list[dict]) -> list[dict]:
    out = []
    for f in config_files:
        if f.get("auto_loaded") and f.get("age_days", 0) > 30:
            out.append({
                "rule": "stale_auto_loaded",
                "severity": Severity.MED,
                "target": f["path"],
                "message": (
                    f"{f['path']} auto-loads but hasn't been edited in "
                    f"{f['age_days']} days. Review for relevance."
                ),
            })
    return out


def _r_home_is_git_repo(home_is_git_repo: bool) -> list[dict]:
    if not home_is_git_repo:
        return []
    return [{
        "rule": "home_is_git_repo",
        "severity": Severity.HIGH,
        "target": "~",
        "message": (
            "Your home directory is itself a git repository. Every project file "
            "you create may end up tracked. Consider moving the .git out."
        ),
    }]


def _r_orphaned_worktree(worktrees: list[dict]) -> list[dict]:
    out = []
    for w in worktrees:
        if w.get("age_days", 0) > 14:
            out.append({
                "rule": "orphaned_worktree",
                "severity": Severity.MED,
                "target": w["path"],
                "message": (
                    f"Worktree at {w['path']} hasn't been touched in "
                    f"{w['age_days']} days. Likely abandoned — consider removing."
                ),
            })
    return out


def _r_dirty_unpushed_stale(repos: list[dict]) -> list[dict]:
    out = []
    for r in repos:
        if r.get("dirty", 0) > 0 and r.get("ahead", 0) > 0 and r.get("age_days", 0) > 7:
            out.append({
                "rule": "dirty_unpushed_stale",
                "severity": Severity.MED,
                "target": r["path"],
                "message": (
                    f"{r['path']} has {r['dirty']} uncommitted change(s) and "
                    f"{r['ahead']} commit(s) ahead of remote, untouched for "
                    f"{r['age_days']} days. Work at risk."
                ),
            })
    return out


def evaluate_all(
    config_files: list[dict],
    repos: list[dict],
    worktrees: list[dict],
    home_is_git_repo: bool,
) -> list[dict]:
    """Run all rules and return the combined findings."""
    findings: list[dict] = []
    findings.extend(_r_auto_loaded_and_large(config_files))
    findings.extend(_r_stale_auto_loaded(config_files))
    findings.extend(_r_home_is_git_repo(home_is_git_repo))
    findings.extend(_r_orphaned_worktree(worktrees))
    findings.extend(_r_dirty_unpushed_stale(repos))
    severity_order = {Severity.HIGH: 0, Severity.MED: 1, Severity.LOW: 2}
    findings.sort(key=lambda x: severity_order.get(x["severity"], 9))
    return findings
