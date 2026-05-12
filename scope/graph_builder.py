"""Pure-function graph builder from scanner outputs to graph JSON.

Converts scanner output (config files, repos, worktrees, processes, findings)
into a node-link diagram suitable for Cytoscape.js visualization.

No filesystem access, no Flask. Pure aggregation over dicts.
"""
from __future__ import annotations
from typing import Optional


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


def _find_parent_repo(worktree_path: str, repos: list[dict]) -> Optional[str]:
    """Find a parent repo by longest-prefix matching.

    Returns the repo node id if found, else None.
    """
    best_match = None
    best_len = 0
    for repo in repos:
        repo_path = repo.get("path", "")
        # Check if repo_path is a prefix of worktree_path
        if worktree_path.startswith(repo_path + "/"):
            if len(repo_path) > best_len:
                best_match = repo
                best_len = len(repo_path)

    if best_match:
        return f"repo:{best_match['path']}"
    return None


def _config_node(file: dict, severity: Optional[str]) -> dict:
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
    }


def _repo_node(repo: dict, severity: Optional[str]) -> dict:
    """Build a repo node from a repo dict."""
    path = repo["path"]
    label = path.split("/")[-1]  # basename
    return {
        "id": f"repo:{path}",
        "label": label,
        "type": "repo",
        "path": path,
        "branch": repo.get("branch", ""),
        "dirty": repo.get("dirty", 0),
        "ahead": repo.get("ahead", 0),
        "behind": repo.get("behind", 0),
        "stale": repo.get("stale", False),
        "severity": severity,
        "has_process": False,  # Updated later if a process matches
    }


def _worktree_node(worktree: dict, parent_repo_id: Optional[str], severity: Optional[str]) -> dict:
    """Build a worktree node from a worktree dict."""
    path = worktree["path"]
    label = path.split("/")[-1]  # basename
    return {
        "id": f"worktree:{path}",
        "label": label,
        "type": "worktree",
        "path": path,
        "parent_repo_id": parent_repo_id,
        "branch": worktree.get("branch", ""),
        "dirty": worktree.get("dirty", 0),
        "severity": severity,
    }


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

    Returns:
        Dict with "nodes" (list) and "edges" (list) keys.
    """
    nodes: list[dict] = []
    edges: list[dict] = []

    # Start with the home node
    nodes.append({
        "id": "home",
        "label": "~",
        "type": "home",
    })

    # Build severity map
    severity_map = _severity_map(findings)

    # Track config files to avoid double-adding and to find which belong to repos
    config_by_path: dict[str, dict] = {}

    # Add config nodes (both claude_files and project_md)
    all_configs = claude_files + project_md
    for config in all_configs:
        config_path = config["path"]
        severity = severity_map.get(config_path)
        node = _config_node(config, severity)
        nodes.append(node)
        config_by_path[config_path] = config

    # Add repo nodes and track by path for later reference
    repo_by_path: dict[str, dict] = {}
    for repo in repos:
        repo_path = repo["path"]
        severity = severity_map.get(repo_path)
        node = _repo_node(repo, severity)
        nodes.append(node)
        repo_by_path[repo_path] = node

    # Add worktree nodes
    for worktree in worktrees:
        worktree_path = worktree["path"]
        severity = severity_map.get(worktree_path)
        parent_repo_id = _find_parent_repo(worktree_path, repos)
        node = _worktree_node(worktree, parent_repo_id, severity)
        nodes.append(node)

    # Add process nodes
    process_by_pid: dict[int, dict] = {}
    for process in processes:
        pid = process["pid"]
        cwd = process.get("cwd", "")

        # Find if cwd matches any repo exactly
        attached_to_id = None
        if cwd in repo_by_path:
            attached_to_id = f"repo:{cwd}"

        node = _process_node(process, attached_to_id)
        nodes.append(node)
        process_by_pid[pid] = node

    # Build edges
    # --- Config node edges ---
    for config_path, config in config_by_path.items():
        config_id = f"config:{config_path}"

        # Check if this config lives inside a repo
        parent_repo_id = None
        for repo_path in repo_by_path.keys():
            # Is config_path inside repo_path?
            if config_path.startswith(repo_path + "/"):
                # Keep longest match
                if parent_repo_id is None or len(repo_path) > len(parent_repo_id.replace("repo:", "")):
                    parent_repo_id = f"repo:{repo_path}"

        if parent_repo_id:
            edges.append({
                "source": parent_repo_id,
                "target": config_id,
            })
        else:
            edges.append({
                "source": "home",
                "target": config_id,
            })

    # --- Repo node edges (all attach to home for now; may change if repo itself is nested) ---
    for repo_path in repo_by_path.keys():
        repo_id = f"repo:{repo_path}"
        edges.append({
            "source": "home",
            "target": repo_id,
        })

    # --- Worktree node edges ---
    for worktree in worktrees:
        worktree_id = f"worktree:{worktree['path']}"
        worktree_node = [n for n in nodes if n["id"] == worktree_id][0]
        parent_repo_id = worktree_node["parent_repo_id"]

        if parent_repo_id:
            edges.append({
                "source": parent_repo_id,
                "target": worktree_id,
                "style": "dashed",
            })
        else:
            edges.append({
                "source": "home",
                "target": worktree_id,
                "style": "dashed",
            })

    # --- Process node edges & update repo has_process ---
    for process in processes:
        pid = process["pid"]
        process_id = f"process:{pid}"
        process_node = process_by_pid[pid]
        attached_to_id = process_node["attached_to_id"]

        if attached_to_id:
            # Update the repo node's has_process flag
            for node in nodes:
                if node["id"] == attached_to_id:
                    node["has_process"] = True
            edges.append({
                "source": attached_to_id,
                "target": process_id,
                "style": "process",
            })
        else:
            edges.append({
                "source": "home",
                "target": process_id,
                "style": "process",
            })

    return {
        "nodes": nodes,
        "edges": edges,
    }
