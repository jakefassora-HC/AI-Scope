"""Pure-function graph builder from scanner outputs to graph JSON.

Converts scanner output (config files, repos, worktrees, processes, findings)
into a node-link diagram suitable for Cytoscape.js visualization.

No filesystem access, no Flask. Pure aggregation over dicts.
"""
from __future__ import annotations
from typing import Callable, Optional


def _severity_map(findings: list[dict]) -> dict[str, str]:
    """Build a path → highest_severity map from findings.

    Severity rank: HIGH > MED > LOW.
    """
    path_to_severity: dict[str, str] = {}
    for finding in findings:
        target = finding.get("target")
        if not target:
            continue
        severity_val = finding.get("severity")
        if not severity_val:
            continue
        # Handle both string and enum forms
        severity = str(severity_val).strip()

        current = path_to_severity.get(target)
        if current is None:
            path_to_severity[target] = severity
        else:
            # Keep highest severity
            rank = {"HIGH": 3, "MED": 2, "LOW": 1}
            if rank.get(severity, 0) > rank.get(current, 0):
                path_to_severity[target] = severity

    return path_to_severity


def _find_parent_repo_path(path: str, repos: list[dict]) -> Optional[str]:
    """Find the parent repo path by longest-prefix matching.

    Returns the repo path string if found, else None.
    """
    best_match = None
    best_len = 0
    for repo in repos:
        repo_path = repo.get("path", "")
        if path.startswith(repo_path + "/"):
            if len(repo_path) > best_len:
                best_match = repo_path
                best_len = len(repo_path)
    return best_match


def _config_node(file: dict, severity: Optional[str], parent: Optional[str]) -> dict:
    """Build a config node from a file dict."""
    return {
        "id": f"config:{file['path']}",
        "label": file.get("name", file["path"].split("/")[-1]),
        "type": "config",
        "path": file["path"],
        "size_bytes": file.get("size_bytes", 0),
        "tokens_est": file.get("tokens_est", 0),
        "age_days": file.get("age_days", 0),
        "severity": severity,
        "parent": parent,
    }


def _region_node(
    path: str,
    label: str,
    parent: Optional[str],
    severity: Optional[str] = None,
    repo: Optional[dict] = None,
) -> dict:
    """Build a region node."""
    node: dict = {
        "id": f"region:{path}",
        "label": label,
        "type": "region",
        "path": path,
        "parent": parent,
        "severity": severity,
        "has_process": False,
    }
    if repo is not None:
        node["branch"] = repo.get("branch", "")
        node["dirty"] = repo.get("dirty", 0)
        node["ahead"] = repo.get("ahead", 0)
        node["behind"] = repo.get("behind", 0)
        node["stale"] = repo.get("stale", False)
    return node


def _process_node(process: dict, attached_to_id: Optional[str]) -> dict:
    """Build a process node from a process dict."""
    pid = process["pid"]
    return {
        "id": f"process:{pid}",
        "label": f"claude ({pid})",
        "type": "process",
        "pid": pid,
        "cwd": process.get("cwd", ""),
        "attached_to_id": attached_to_id,
    }


def build_graph(
    *,
    claude_files: list[dict],
    project_md: list[dict],
    repos: list[dict],
    worktrees: list[dict],
    processes: list[dict],
    findings: list[dict],
    home_path: str,
    list_landmarks: Optional[Callable[[str], list[dict]]] = None,
) -> dict:
    """Build a node-link graph from scanner outputs.

    Args:
        claude_files: List of config dicts from scan_claude_dir
        project_md: List of config dicts from find_claude_md_files
        repos: List of repo dicts from find_repos
        worktrees: List of worktree dicts (repo-format)
        processes: List of process dicts from find_claude_processes
        findings: List of finding dicts with target and severity
        home_path: User's home directory path (e.g., "/Users/x")
        list_landmarks: Optional callable(repo_path) -> list[file_dict].
            Called per repo to surface landmark files as config nodes.
            Defaults to a no-op if None.

    Returns:
        Dict with "nodes" (list) and "edges" (list) keys.
    """
    if list_landmarks is None:
        list_landmarks = lambda _: []

    nodes: list[dict] = []
    edges: list[dict] = []

    # Home node (identity/label — no edges emitted from it)
    nodes.append({
        "id": "home",
        "label": "~",
        "type": "home",
    })

    # Build severity map
    severity_map = _severity_map(findings)

    # --- Top-level region nodes ---
    nodes.append(_region_node(".claude", ".claude", parent=None))
    nodes.append(_region_node("projects", "projects", parent=None))

    # --- Rules sub-region inside .claude ---
    rules_region_id = "region:.claude/rules"
    rules_region_emitted = False
    rules_prefix = f"{home_path}/.claude/rules/"

    def _ensure_rules_region() -> None:
        nonlocal rules_region_emitted
        if not rules_region_emitted:
            nodes.append(_region_node(".claude/rules", "rules", parent="region:.claude"))
            rules_region_emitted = True

    # --- claude_files → config nodes under region:.claude ---
    claude_file_paths: set[str] = set()
    for f in claude_files:
        fpath = f["path"]
        claude_file_paths.add(fpath)
        severity = severity_map.get(fpath)
        if fpath.startswith(rules_prefix):
            _ensure_rules_region()
            parent = rules_region_id
        else:
            parent = "region:.claude"
        nodes.append(_config_node(f, severity, parent=parent))

    # --- Repo regions ---
    repo_region_by_path: dict[str, dict] = {}  # path → region node
    for repo in repos:
        repo_path = repo["path"]
        severity = severity_map.get(repo_path)
        label = repo_path.split("/")[-1]
        node = _region_node(repo_path, label, parent="region:projects", severity=severity, repo=repo)
        nodes.append(node)
        repo_region_by_path[repo_path] = node

        # Landmark files for this repo
        landmark_paths: set[str] = set()
        for lm in list_landmarks(repo_path):
            lm_path = lm["path"]
            landmark_paths.add(lm_path)
            lm_severity = severity_map.get(lm_path)
            nodes.append(_config_node(lm, lm_severity, parent=f"region:{repo_path}"))

        # project_md files that belong to this repo (de-dup with landmarks)
        for pm in project_md:
            pm_path = pm["path"]
            if pm_path.startswith(repo_path + "/") and pm_path not in landmark_paths and pm_path not in claude_file_paths:
                pm_severity = severity_map.get(pm_path)
                nodes.append(_config_node(pm, pm_severity, parent=f"region:{repo_path}"))
                landmark_paths.add(pm_path)  # prevent double-add if repos overlap

    # project_md files not matched to any repo → under region:projects
    all_repo_paths = list(repo_region_by_path.keys())
    emitted_pm_paths: set[str] = {
        n["path"] for n in nodes if n.get("type") == "config" and n.get("path")
    }
    for pm in project_md:
        pm_path = pm["path"]
        if pm_path in emitted_pm_paths or pm_path in claude_file_paths:
            continue
        pm_severity = severity_map.get(pm_path)
        nodes.append(_config_node(pm, pm_severity, parent="region:projects"))

    # --- Worktree regions ---
    for worktree in worktrees:
        wt_path = worktree["path"]
        severity = severity_map.get(wt_path)
        label = wt_path.split("/")[-1]
        parent_repo_path = _find_parent_repo_path(wt_path, repos)
        parent = f"region:{parent_repo_path}" if parent_repo_path else "region:projects"
        nodes.append(_region_node(wt_path, label, parent=parent, severity=severity, repo=worktree))

    # --- Process nodes ---
    process_by_pid: dict[int, dict] = {}
    for process in processes:
        pid = process["pid"]
        cwd = process.get("cwd", "")
        attached_to_id = f"region:{cwd}" if cwd in repo_region_by_path else None
        node = _process_node(process, attached_to_id)
        nodes.append(node)
        process_by_pid[pid] = node

    # --- Edges: only process edges remain ---
    for process in processes:
        pid = process["pid"]
        process_id = f"process:{pid}"
        process_node = process_by_pid[pid]
        attached_to_id = process_node["attached_to_id"]

        if attached_to_id:
            # Mark the region as having a process
            for node in nodes:
                if node["id"] == attached_to_id:
                    node["has_process"] = True
            edges.append({
                "source": attached_to_id,
                "target": process_id,
                "style": "process",
            })
        # Unattached processes get no edge (they're top-level orphans)

    return {
        "nodes": nodes,
        "edges": edges,
    }
