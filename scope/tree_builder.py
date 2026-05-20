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


def _plan_file_leaf(f: dict, severity: Optional[str], claude_active: bool = False) -> dict:
    size = max(1, int(f.get("size_bytes", 1) or 1))
    return {
        "name": f.get("name") or f["path"].split("/")[-1],
        "kind": "plan",
        "path": f["path"],
        "rel": f.get("rel", ""),
        "ext": f.get("ext", "md"),
        "value": size,
        "size_bytes": size,
        "tokens_est": f.get("tokens_est", 0),
        "age_days": f.get("age_days", 0),
        "phase": f.get("phase"),
        "phase_status": f.get("phase_status"),
        "severity": severity,
        "claude_active": claude_active,
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
    list_plan_files: Optional[Callable[[str], list[dict]]] = None,
) -> dict:
    """Build a d3.hierarchy-shaped tree from scanner outputs."""
    if list_landmarks is None:
        list_landmarks = lambda _: []
    if scan_planning is None:
        scan_planning = lambda _: None
    if list_plan_files is None:
        list_plan_files = lambda _: []

    sev = _severity_map(findings)
    proc_cwds = {p.get("cwd", "") for p in processes}
    # paths of plan files currently held open by any claude process
    open_plan_paths: set[str] = set()
    for p in processes:
        for path in p.get("open_plans", []) or []:
            open_plan_paths.add(path)

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

        children: list[dict] = []

        # Plans = all md/html docs in planning-like folders. Group by phase
        # when the file lives under .planning/phases/<phase>/.
        plan_files = list_plan_files(rpath)
        planning = scan_planning(rpath)
        if plan_files or (planning and planning.get("phases")):
            phase_meta_by_name: dict[str, dict] = {}
            if planning and planning.get("phases"):
                for p in planning["phases"]:
                    phase_meta_by_name[p["name"]] = p
            phase_status_by_name = {n: m.get("status", "idle") for n, m in phase_meta_by_name.items()}

            # bucket plan files: loose vs by phase
            loose_files: list[dict] = []
            by_phase: dict[str, list[dict]] = {}
            for pf in plan_files:
                active = pf["path"] in open_plan_paths
                # Override the legacy phase_status with the git-aware status
                # from scan_planning so leaf colors match phase colors.
                if pf.get("phase") and pf["phase"] in phase_status_by_name:
                    pf = dict(pf, phase_status=phase_status_by_name[pf["phase"]])
                leaf = _plan_file_leaf(pf, sev.get(pf["path"]), claude_active=active)
                if pf.get("phase"):
                    by_phase.setdefault(pf["phase"], []).append(leaf)
                else:
                    loose_files.append(leaf)

            phase_children: list[dict] = []
            for phase_name in sorted(set(list(by_phase.keys()) + list(phase_status_by_name.keys()))):
                status = phase_status_by_name.get(phase_name, "idle")
                meta = phase_meta_by_name.get(phase_name, {})
                phase_children.append({
                    "name": phase_name,
                    "kind": "phase",
                    "status": status,
                    "repo": rpath,                        # for /api/phase-commits
                    "repo_name": rpath.split("/")[-1],    # display label
                    "last_commit_at": meta.get("last_commit_at", 0),
                    "commit_count": meta.get("commit_count", 0),
                    "referenced_in_commits": meta.get("referenced_in_commits", 0),
                    "merged_to_main": meta.get("merged_to_main", False),
                    "children": by_phase.get(phase_name, [{
                        "name": "(no files)", "kind": "placeholder", "value": 1,
                    }]),
                })

            plans_children = list(loose_files) + phase_children
            label = "plans"
            milestone = (planning or {}).get("milestone") or ""
            percent = (planning or {}).get("percent", 0) if planning else 0
            if milestone:
                label = f"plans · {milestone} · {percent}%"

            children.append({
                "name": label,
                "kind": "group",
                "subtitle": (planning or {}).get("status", ""),
                "milestone": milestone,
                "percent": percent,
                "completed_phases": (planning or {}).get("completed_phases", 0) if planning else 0,
                "total_phases": (planning or {}).get("total_phases", len(phase_children)) if planning else len(phase_children),
                "file_count": len(plan_files),
                "children": plans_children,
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
