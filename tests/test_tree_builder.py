"""Tests for tree_builder — pure-function shape verification."""
from __future__ import annotations
from scope.tree_builder import build_tree


HOME = "/Users/test"


def _file(path: str, size: int = 100, tokens: int = 25) -> dict:
    return {
        "path": path,
        "name": path.split("/")[-1],
        "size_bytes": size,
        "tokens_est": tokens,
        "age_days": 0,
    }


def _empty(**overrides) -> dict:
    base = dict(
        claude_files=[],
        project_md=[],
        repos=[],
        worktrees=[],
        processes=[],
        findings=[],
        home_path=HOME,
    )
    base.update(overrides)
    return base


def test_root_shape():
    t = build_tree(**_empty())
    assert t["name"] == "~"
    assert t["kind"] == "root"
    kinds = [c["kind"] for c in t["children"]]
    assert kinds == ["region", "region"]
    assert t["children"][0]["name"] == ".claude"
    assert t["children"][1]["name"] == "projects"


def test_claude_files_split_into_rules():
    files = [
        _file(f"{HOME}/.claude/CLAUDE.md"),
        _file(f"{HOME}/.claude/rules/workflow.md"),
    ]
    t = build_tree(**_empty(claude_files=files))
    claude = t["children"][0]
    names = [c["name"] for c in claude["children"]]
    assert "CLAUDE.md" in names
    rules_region = next(c for c in claude["children"] if c["name"] == "rules")
    assert rules_region["kind"] == "region"
    assert [c["name"] for c in rules_region["children"]] == ["workflow.md"]


def test_repo_with_plan_files_and_planning():
    repo = {"path": "/Users/test/projects/foo", "branch": "main", "dirty": 0,
            "untracked": 0, "ahead": 0, "behind": 0, "stale": False}
    plan_files = [
        {"path": "/Users/test/projects/foo/CLAUDE.md", "name": "CLAUDE.md",
         "size_bytes": 100, "tokens_est": 25, "age_days": 0, "ext": "md", "phase": None},
        {"path": "/Users/test/projects/foo/.planning/phases/01-x/01-PLAN.md",
         "name": "01-PLAN.md", "size_bytes": 200, "tokens_est": 50, "age_days": 0,
         "ext": "md", "phase": "01-x", "phase_status": "complete"},
        {"path": "/Users/test/projects/foo/.planning/phases/02-y/02-PLAN.md",
         "name": "02-PLAN.md", "size_bytes": 150, "tokens_est": 40, "age_days": 0,
         "ext": "md", "phase": "02-y", "phase_status": "iterating"},
    ]
    planning = {
        "milestone": "v1.0", "status": "executing", "percent": 50,
        "total_phases": 2, "completed_phases": 1,
        "phases": [
            {"name": "01-x", "status": "complete", "path": "/.../01-x"},
            {"name": "02-y", "status": "iterating", "path": "/.../02-y"},
        ],
    }
    t = build_tree(**_empty(
        repos=[repo],
        scan_planning=lambda p: planning if p == repo["path"] else None,
        list_plan_files=lambda p: plan_files if p == repo["path"] else [],
    ))
    foo = t["children"][1]["children"][0]
    plans = next(g for g in foo["children"] if g["name"].startswith("plans"))
    assert plans["percent"] == 50
    assert plans["file_count"] == 3
    # Loose CLAUDE.md leaf + two phase children
    kinds = [c["kind"] for c in plans["children"]]
    assert kinds.count("plan") == 1  # CLAUDE.md loose
    assert kinds.count("phase") == 2
    phase_01 = next(c for c in plans["children"] if c.get("name") == "01-x")
    assert phase_01["status"] == "complete"
    assert phase_01["children"][0]["name"] == "01-PLAN.md"
    assert phase_01["children"][0]["kind"] == "plan"


def test_process_marks_repo_has_process():
    repo = {"path": "/Users/test/projects/foo", "branch": "main", "dirty": 0,
            "untracked": 0, "ahead": 0, "behind": 0, "stale": False}
    procs = [{"pid": 999, "cwd": "/Users/test/projects/foo"}]
    t = build_tree(**_empty(repos=[repo], processes=procs))
    foo = t["children"][1]["children"][0]
    assert foo["has_process"] is True


def test_orphan_process_emits_region():
    procs = [{"pid": 42, "cwd": "/somewhere/else"}]
    t = build_tree(**_empty(processes=procs))
    assert any(c["name"] == "claude processes" for c in t["children"])


def test_severity_applied_to_file():
    f = _file(f"{HOME}/.claude/CLAUDE.md")
    findings = [{"target": f["path"], "severity": "HIGH", "rule": "x", "message": "y"}]
    t = build_tree(**_empty(claude_files=[f], findings=findings))
    claude_md = t["children"][0]["children"][0]
    assert claude_md["severity"] == "HIGH"


def test_worktree_nested_under_repo():
    repo = {"path": "/Users/test/projects/foo", "branch": "main", "dirty": 0,
            "untracked": 0, "ahead": 0, "behind": 0, "stale": False}
    wt = {"path": "/Users/test/projects/foo/wt-feature", "branch": "feature",
          "dirty": 1, "untracked": 0, "ahead": 0, "behind": 0, "stale": False}
    t = build_tree(**_empty(repos=[repo], worktrees=[wt]))
    foo = t["children"][1]["children"][0]
    wt_group = next(g for g in foo["children"] if g["name"] == "worktrees")
    assert wt_group["children"][0]["kind"] == "worktree"
    assert wt_group["children"][0]["branch"] == "feature"


def test_empty_repo_has_placeholder():
    repo = {"path": "/Users/test/projects/foo", "branch": "main", "dirty": 0,
            "untracked": 0, "ahead": 0, "behind": 0, "stale": False}
    t = build_tree(**_empty(repos=[repo]))
    foo = t["children"][1]["children"][0]
    assert foo["children"][0]["kind"] == "placeholder"
