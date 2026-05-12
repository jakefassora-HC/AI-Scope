"""Tests for scope.graph_builder."""
import pytest
from scope.graph_builder import build_graph


def test_empty_inputs_just_home_node():
    """Empty scanner output → exactly one home node, zero edges."""
    result = build_graph(
        claude_files=[],
        project_md=[],
        repos=[],
        worktrees=[],
        processes=[],
        findings=[],
        home_path="/Users/test",
    )
    assert len(result["nodes"]) == 1
    assert result["nodes"][0]["id"] == "home"
    assert result["nodes"][0]["label"] == "~"
    assert result["nodes"][0]["type"] == "home"
    assert len(result["edges"]) == 0


def test_single_config_file_attaches_to_home():
    """One claude_file under ~/.claude/ → 2 nodes (home + config), 1 edge home→config."""
    claude_files = [
        {
            "path": "/Users/test/.claude/CLAUDE.md",
            "name": "CLAUDE.md",
            "size_bytes": 512,
            "tokens_est": 200,
            "age_days": 5,
            "auto_loaded": True,
        }
    ]
    result = build_graph(
        claude_files=claude_files,
        project_md=[],
        repos=[],
        worktrees=[],
        processes=[],
        findings=[],
        home_path="/Users/test",
    )
    assert len(result["nodes"]) == 2
    node_ids = {n["id"] for n in result["nodes"]}
    assert "home" in node_ids
    assert "config:/Users/test/.claude/CLAUDE.md" in node_ids

    config_node = [n for n in result["nodes"] if n["id"] == "config:/Users/test/.claude/CLAUDE.md"][0]
    assert config_node["label"] == "CLAUDE.md"
    assert config_node["type"] == "config"
    assert config_node["path"] == "/Users/test/.claude/CLAUDE.md"
    assert config_node["size_bytes"] == 512
    assert config_node["tokens_est"] == 200

    assert len(result["edges"]) == 1
    assert result["edges"][0]["source"] == "home"
    assert result["edges"][0]["target"] == "config:/Users/test/.claude/CLAUDE.md"


def test_project_claude_md_attaches_to_its_repo():
    """repo at /Users/x/projects/foo + project_md at /Users/x/projects/foo/CLAUDE.md
    → config edge source is the repo, NOT home."""
    repos = [
        {
            "path": "/Users/test/projects/foo",
            "branch": "main",
            "dirty": 0,
            "untracked": 0,
            "ahead": 0,
            "behind": 0,
            "stash_count": 0,
            "worktree_count": 1,
            "last_commit_iso": "2026-05-10T00:00:00+00:00",
            "age_days": 2,
            "stale": False,
        }
    ]
    project_md = [
        {
            "path": "/Users/test/projects/foo/CLAUDE.md",
            "name": "CLAUDE.md",
            "size_bytes": 1024,
            "tokens_est": 400,
            "age_days": 2,
            "auto_loaded": False,
        }
    ]
    result = build_graph(
        claude_files=[],
        project_md=project_md,
        repos=repos,
        worktrees=[],
        processes=[],
        findings=[],
        home_path="/Users/test",
    )

    # Expect 3 nodes: home, repo, config
    assert len(result["nodes"]) == 3
    node_ids = {n["id"] for n in result["nodes"]}
    assert "home" in node_ids
    assert "repo:/Users/test/projects/foo" in node_ids
    assert "config:/Users/test/projects/foo/CLAUDE.md" in node_ids

    # Expect 2 edges: home → repo, repo → config (NOT home → config)
    assert len(result["edges"]) == 2
    edges_from = {(e["source"], e["target"]) for e in result["edges"]}
    assert ("home", "repo:/Users/test/projects/foo") in edges_from
    assert ("repo:/Users/test/projects/foo", "config:/Users/test/projects/foo/CLAUDE.md") in edges_from


def test_worktree_with_resolvable_parent():
    """repo at /Users/x/projects/foo + worktree as nested checkout at /Users/x/projects/foo/.worktrees/fix-x
    → worktree has parent_repo_id set; edge from repo to worktree with style="dashed"."""
    repos = [
        {
            "path": "/Users/test/projects/foo",
            "branch": "main",
            "dirty": 0,
            "untracked": 0,
            "ahead": 0,
            "behind": 0,
            "stash_count": 0,
            "worktree_count": 2,
            "last_commit_iso": "2026-05-10T00:00:00+00:00",
            "age_days": 2,
            "stale": False,
        }
    ]
    worktrees = [
        {
            "path": "/Users/test/projects/foo/.worktrees/fix-x",
            "branch": "fix-x",
            "dirty": 0,
            "untracked": 0,
            "age_days": 1,
        }
    ]
    result = build_graph(
        claude_files=[],
        project_md=[],
        repos=repos,
        worktrees=worktrees,
        processes=[],
        findings=[],
        home_path="/Users/test",
    )

    # Expect 3 nodes: home, repo, worktree
    assert len(result["nodes"]) == 3
    worktree_node = [n for n in result["nodes"] if n["id"] == "worktree:/Users/test/projects/foo/.worktrees/fix-x"][0]
    assert worktree_node["parent_repo_id"] == "repo:/Users/test/projects/foo"
    assert worktree_node["type"] == "worktree"

    # Expect 2 edges: home → repo, repo → worktree (dashed)
    assert len(result["edges"]) == 2
    dashed_edge = [e for e in result["edges"] if e.get("style") == "dashed"]
    assert len(dashed_edge) == 1
    assert dashed_edge[0]["source"] == "repo:/Users/test/projects/foo"
    assert dashed_edge[0]["target"] == "worktree:/Users/test/projects/foo/.worktrees/fix-x"


def test_worktree_without_parent_attaches_to_home():
    """worktree at /Users/x/.claude/worktrees/orphan, no matching repo
    → edge from home with style="dashed", parent_repo_id is None."""
    worktrees = [
        {
            "path": "/Users/test/.claude/worktrees/orphan",
            "branch": "orphan-branch",
            "dirty": 0,
            "untracked": 0,
            "age_days": 1,
        }
    ]
    result = build_graph(
        claude_files=[],
        project_md=[],
        repos=[],
        worktrees=worktrees,
        processes=[],
        findings=[],
        home_path="/Users/test",
    )

    # Expect 2 nodes: home, worktree
    assert len(result["nodes"]) == 2
    worktree_node = [n for n in result["nodes"] if n["type"] == "worktree"][0]
    assert worktree_node["parent_repo_id"] is None

    # Expect 1 edge: home → worktree (dashed)
    assert len(result["edges"]) == 1
    assert result["edges"][0]["source"] == "home"
    assert result["edges"][0]["target"] == "worktree:/Users/test/.claude/worktrees/orphan"
    assert result["edges"][0]["style"] == "dashed"


def test_process_cwd_matches_repo_sets_has_process():
    """process with cwd=/Users/x/projects/foo and a repo at that path
    → repo node has_process=True, process node attached_to_id is repo's id, edge style="process"."""
    repos = [
        {
            "path": "/Users/test/projects/foo",
            "branch": "main",
            "dirty": 0,
            "untracked": 0,
            "ahead": 0,
            "behind": 0,
            "stash_count": 0,
            "worktree_count": 1,
            "last_commit_iso": "2026-05-10T00:00:00+00:00",
            "age_days": 2,
            "stale": False,
        }
    ]
    processes = [
        {
            "pid": 4821,
            "cmdline": "claude code",
            "cwd": "/Users/test/projects/foo",
            "uptime_sec": 120,
        }
    ]
    result = build_graph(
        claude_files=[],
        project_md=[],
        repos=repos,
        worktrees=[],
        processes=processes,
        findings=[],
        home_path="/Users/test",
    )

    # Expect 3 nodes: home, repo, process
    assert len(result["nodes"]) == 3
    repo_node = [n for n in result["nodes"] if n["id"] == "repo:/Users/test/projects/foo"][0]
    assert repo_node["has_process"] is True

    process_node = [n for n in result["nodes"] if n["type"] == "process"][0]
    assert process_node["attached_to_id"] == "repo:/Users/test/projects/foo"
    assert process_node["pid"] == 4821
    assert process_node["label"] == "claude (4821)"

    # Expect 2 edges: home → repo, repo → process (style="process")
    assert len(result["edges"]) == 2
    process_edge = [e for e in result["edges"] if e.get("style") == "process"]
    assert len(process_edge) == 1
    assert process_edge[0]["source"] == "repo:/Users/test/projects/foo"
    assert process_edge[0]["target"] == "process:4821"


def test_process_cwd_no_match_attaches_to_home():
    """process cwd=/tmp → attached_to_id is None, edge from home."""
    processes = [
        {
            "pid": 5555,
            "cmdline": "claude code",
            "cwd": "/tmp",
            "uptime_sec": 60,
        }
    ]
    result = build_graph(
        claude_files=[],
        project_md=[],
        repos=[],
        worktrees=[],
        processes=processes,
        findings=[],
        home_path="/Users/test",
    )

    # Expect 2 nodes: home, process
    assert len(result["nodes"]) == 2
    process_node = [n for n in result["nodes"] if n["type"] == "process"][0]
    assert process_node["attached_to_id"] is None

    # Expect 1 edge: home → process (style="process")
    assert len(result["edges"]) == 1
    assert result["edges"][0]["source"] == "home"
    assert result["edges"][0]["target"] == "process:5555"
    assert result["edges"][0]["style"] == "process"


def test_severity_high_wins_over_med():
    """two findings on same path: one MED, one HIGH → that node's severity is "HIGH"."""
    claude_files = [
        {
            "path": "/Users/test/.claude/CLAUDE.md",
            "name": "CLAUDE.md",
            "size_bytes": 512,
            "tokens_est": 200,
            "age_days": 5,
            "auto_loaded": True,
        }
    ]
    findings = [
        {
            "rule": "rule1",
            "severity": "MED",
            "target": "/Users/test/.claude/CLAUDE.md",
            "message": "medium severity finding",
        },
        {
            "rule": "rule2",
            "severity": "HIGH",
            "target": "/Users/test/.claude/CLAUDE.md",
            "message": "high severity finding",
        },
    ]
    result = build_graph(
        claude_files=claude_files,
        project_md=[],
        repos=[],
        worktrees=[],
        processes=[],
        findings=findings,
        home_path="/Users/test",
    )

    config_node = [n for n in result["nodes"] if n["type"] == "config"][0]
    assert config_node["severity"] == "HIGH"


def test_severity_string_or_enum_handled():
    """test passes findings with severity as plain strings "HIGH"/"MED"."""
    repos = [
        {
            "path": "/Users/test/projects/bar",
            "branch": "main",
            "dirty": 0,
            "untracked": 0,
            "ahead": 0,
            "behind": 0,
            "stash_count": 0,
            "worktree_count": 1,
            "last_commit_iso": "2026-05-10T00:00:00+00:00",
            "age_days": 2,
            "stale": False,
        }
    ]
    findings = [
        {
            "rule": "stale_repo",
            "severity": "MED",  # plain string, not an enum
            "target": "/Users/test/projects/bar",
            "message": "repo is stale",
        }
    ]
    result = build_graph(
        claude_files=[],
        project_md=[],
        repos=repos,
        worktrees=[],
        processes=[],
        findings=findings,
        home_path="/Users/test",
    )

    repo_node = [n for n in result["nodes"] if n["type"] == "repo"][0]
    assert repo_node["severity"] == "MED"
