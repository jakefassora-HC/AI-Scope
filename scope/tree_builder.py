"""Pure-function tree builder for the D3 zoomable treemap.

Shape: d3.hierarchy-compatible. Each node has `name`, optional `children`,
and at leaves `value` (numeric — used by d3.treemap layout).

No filesystem access: scanner outputs in, tree out.
"""
from __future__ import annotations
from typing import Callable, Optional


def _severity_map(findings: list[dict]) -> dict[str, str]:
    rank = {"HIGH": 3, "MED": 2, "LOW": 1}
    out: dict[str, str] = {}
    for f in findings:
        target = f.get("target")
        sev = f.get("severity")
        if not target or not sev:
            continue
        sev = str(sev).strip()
        if rank.get(sev, 0) > rank.get(out.get(target, ""), 0):
            out[target] = sev
    return out


def _file_leaf(f: dict, severity: Optional[str]) -> dict:
    size = max(1, int(f.get("size_bytes", 1) or 1))
    return {
        "name": f.get("name") or f["path"].split("/")[-1],
        "kind": "file",
        "path": f["path"],
        "value": size,
        "size_bytes": size,
        "tokens_est": f.get("tokens_est", 0),
        "age_days": f.get("age_days", 0),
        "severity": severity,
    }


def _repo_meta(repo: dict, severity: Optional[str], has_process: bool) -> dict:
    return {
        "branch": repo.get("branch", ""),
        "dirty": repo.get("dirty", 0),
        "untracked": repo.get("untracked", 0),
        "ahead": repo.get("ahead", 0),
        "behind": repo.get("behind", 0),
        "stale": bool(repo.get("stale", False)),
        "severity": severity,
        "has_process": has_process,
    }


def _phase_leaf(phase: dict) -> dict:
    return {
        "name": phase["name"],
        "kind": "phase",
        "status": phase.get("status", "draft"),
        "path": phase.get("path", ""),
        "value": 1,
    }


def build_tree(
    *,
    claude_files: list[dict],
    project_md: list[dict],
    repos: list[dict],
    worktrees: list[dict],
    processes: list[dict],
    findings: list[dict],
    home_path: str,
    list_landmarks: Optional[Callable[[str], list[dict]]] = None,
    scan_planning: Optional[Callable[[str], Optional[dict]]] = None,
) -> dict:
    """Build a d3.hierarchy-shaped tree from scanner outputs."""
    if list_landmarks is None:
        list_landmarks = lambda _: []
    if scan_planning is None:
        scan_planning = lambda _: None

    sev = _severity_map(findings)
    proc_cwds = {p.get("cwd", "") for p in processes}

    # --- .claude region ---
    rules_prefix = f"{home_path}/.claude/rules/"
    claude_root_files: list[dict] = []
    rules_files: list[dict] = []
    for f in claude_files:
        leaf = _file_leaf(f, sev.get(f["path"]))
        (rules_files if f["path"].startswith(rules_prefix) else claude_root_files).append(leaf)

    claude_children: list[dict] = list(claude_root_files)
    if rules_files:
        claude_children.append({
            "name": "rules",
            "kind": "region",
            "children": rules_files,
        })

    claude_region = {
        "name": ".claude",
        "kind": "region",
        "subtitle": "global config · auto-loaded each turn",
        "children": claude_children or [{
            "name": "(empty)", "kind": "placeholder", "value": 1,
        }],
    }

    # --- projects region ---
    claude_file_paths = {f["path"] for f in claude_files}
    repo_children: list[dict] = []
    for repo in repos:
        rpath = repo["path"]
        has_proc = rpath in proc_cwds
        rsev = sev.get(rpath)

        # human files: landmarks + project_md that live in this repo
        landmark_paths: set[str] = set()
        files: list[dict] = []
        for lm in list_landmarks(rpath):
            landmark_paths.add(lm["path"])
            files.append(_file_leaf(lm, sev.get(lm["path"])))
        for pm in project_md:
            ppath = pm["path"]
            if (
                ppath not in landmark_paths
                and ppath not in claude_file_paths
                and ppath.startswith(rpath + "/")
            ):
                landmark_paths.add(ppath)
                files.append(_file_leaf(pm, sev.get(ppath)))

        children: list[dict] = []
        if files:
            children.append({
                "name": "human files",
                "kind": "group",
                "children": files,
            })

        # plans (GSD .planning)
        planning = scan_planning(rpath)
        if planning and planning.get("phases"):
            label = "plans"
            milestone = planning.get("milestone") or ""
            if milestone:
                label = f"plans · {milestone} · {planning.get('percent', 0)}%"
            children.append({
                "name": label,
                "kind": "group",
                "subtitle": planning.get("status", ""),
                "milestone": milestone,
                "percent": planning.get("percent", 0),
                "completed_phases": planning.get("completed_phases", 0),
                "total_phases": planning.get("total_phases", 0),
                "children": [_phase_leaf(p) for p in planning["phases"]],
            })

        # worktrees attached to this repo
        wt_children = [
            _worktree_node(w, sev.get(w["path"]), w["path"] in proc_cwds)
            for w in worktrees
            if w["path"].startswith(rpath + "/")
        ]
        if wt_children:
            children.append({
                "name": "worktrees",
                "kind": "group",
                "children": wt_children,
            })

        if not children:
            children = [{"name": "(empty)", "kind": "placeholder", "value": 1}]

        repo_node = {
            "name": rpath.split("/")[-1],
            "kind": "repo",
            "path": rpath,
            **_repo_meta(repo, rsev, has_proc),
            "children": children,
        }
        repo_children.append(repo_node)

    # Orphan worktrees (no parent repo in `repos`)
    repo_paths = {r["path"] for r in repos}
    for w in worktrees:
        if not any(w["path"].startswith(rp + "/") for rp in repo_paths):
            repo_children.append(_worktree_node(w, sev.get(w["path"]), w["path"] in proc_cwds))

    if not repo_children:
        repo_children = [{"name": "(no projects)", "kind": "placeholder", "value": 1}]

    projects_region = {
        "name": "projects",
        "kind": "region",
        "subtitle": f"{len([r for r in repo_children if r.get('kind') == 'repo'])} repos",
        "children": repo_children,
    }

    # --- orphan processes (cwd not in any known repo) ---
    known_paths = {r["path"] for r in repos} | {w["path"] for w in worktrees}
    orphan_procs = [p for p in processes if p.get("cwd", "") not in known_paths]
    extra: list[dict] = []
    if orphan_procs:
        extra.append({
            "name": "claude processes",
            "kind": "region",
            "subtitle": f"{len(orphan_procs)} unattached",
            "children": [{
                "name": f"PID {p['pid']}",
                "kind": "process",
                "pid": p["pid"],
                "cwd": p.get("cwd", ""),
                "value": 1,
            } for p in orphan_procs],
        })

    return {
        "name": "~",
        "kind": "root",
        "path": home_path,
        "children": [claude_region, projects_region] + extra,
    }


def _worktree_node(w: dict, severity: Optional[str], has_process: bool) -> dict:
    return {
        "name": w["path"].split("/")[-1],
        "kind": "worktree",
        "path": w["path"],
        **_repo_meta(w, severity, has_process),
        "children": [{"name": "(worktree)", "kind": "placeholder", "value": 1}],
    }
