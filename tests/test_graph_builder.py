"""Tests for scope.graph_builder."""
import pytest
from scope.graph_builder import build_graph

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_FOO = {
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

REPO_BAR = {
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

CLAUDE_MD_FILE = {
    "path": "/Users/test/.claude/CLAUDE.md",
    "name": "CLAUDE.md",
    "size_bytes": 512,
    "tokens_est": 200,
    "age_days": 5,
    "auto_loaded": True,
}

NO_LANDMARKS = lambda _: []


def _base(**kwargs):
    defaults = dict(
        claude_files=[],
        project_md=[],
        repos=[],
        worktrees=[],
        processes=[],
        findings=[],
        home_path="/Users/test",
        list_landmarks=NO_LANDMARKS,
    )
    defaults.update(kwargs)
    return build_graph(**defaults)


def _node(result, node_id):
    return next((n for n in result["nodes"] if n["id"] == node_id), None)


def _nodes_of_type(result, t):
    return [n for n in result["nodes"] if n["type"] == t]


# ---------------------------------------------------------------------------
# Original tests — updated for new shape
# ---------------------------------------------------------------------------

def test_empty_inputs_emits_home_and_two_regions():
    """Empty scanner output → home + region:.claude + region:projects, zero edges."""
    result = _base()
    assert len(result["nodes"]) == 3
    ids = {n["id"] for n in result["nodes"]}
    assert "home" in ids
    assert "region:.claude" in ids
    assert "region:projects" in ids
    assert len(result["edges"]) == 0


def test_single_config_file_parented_under_claude_region():
    """One claude_file → config node with parent == 'region:.claude'."""
    result = _base(claude_files=[CLAUDE_MD_FILE])
    config = _node(result, "config:/Users/test/.claude/CLAUDE.md")
    assert config is not None
    assert config["type"] == "config"
    assert config["parent"] == "region:.claude"
    assert config["label"] == "CLAUDE.md"
    assert config["size_bytes"] == 512
    assert config["tokens_est"] == 200
    # No edges expected
    assert len(result["edges"]) == 0


def test_project_claude_md_parented_under_repo_region():
    """project_md under a repo path → config node parented under that repo's region."""
    project_md = [{
        "path": "/Users/test/projects/foo/CLAUDE.md",
        "name": "CLAUDE.md",
        "size_bytes": 1024,
        "tokens_est": 400,
        "age_days": 2,
        "auto_loaded": False,
    }]
    result = _base(repos=[REPO_FOO], project_md=project_md)

    node_ids = {n["id"] for n in result["nodes"]}
    assert "region:/Users/test/projects/foo" in node_ids
    assert "config:/Users/test/projects/foo/CLAUDE.md" in node_ids

    config = _node(result, "config:/Users/test/projects/foo/CLAUDE.md")
    assert config["parent"] == "region:/Users/test/projects/foo"

    # No home-edges; compound parent conveys structure
    assert len(result["edges"]) == 0


def test_worktree_region_parented_under_parent_repo():
    """worktree nested under a repo → its region parent == that repo's region id."""
    worktrees = [{
        "path": "/Users/test/projects/foo/.worktrees/fix-x",
        "branch": "fix-x",
        "dirty": 0,
        "untracked": 0,
        "age_days": 1,
    }]
    result = _base(repos=[REPO_FOO], worktrees=worktrees)

    wt = _node(result, "region:/Users/test/projects/foo/.worktrees/fix-x")
    assert wt is not None
    assert wt["type"] == "region"
    assert wt["parent"] == "region:/Users/test/projects/foo"

    assert len(result["edges"]) == 0


def test_worktree_without_parent_goes_under_projects():
    """Orphan worktree (no matching repo) → parent == 'region:projects'."""
    worktrees = [{
        "path": "/Users/test/.claude/worktrees/orphan",
        "branch": "orphan-branch",
        "dirty": 0,
        "untracked": 0,
        "age_days": 1,
    }]
    result = _base(worktrees=worktrees)

    wt = _node(result, "region:/Users/test/.claude/worktrees/orphan")
    assert wt is not None
    assert wt["parent"] == "region:projects"

    assert len(result["edges"]) == 0


def test_process_attaches_to_region_and_sets_flag():
    """process cwd matches repo → region has_process=True, edge process-style emitted."""
    processes = [{
        "pid": 4821,
        "cmdline": "claude code",
        "cwd": "/Users/test/projects/foo",
        "uptime_sec": 120,
    }]
    result = _base(repos=[REPO_FOO], processes=processes)

    region = _node(result, "region:/Users/test/projects/foo")
    assert region["has_process"] is True

    proc = _node(result, "process:4821")
    assert proc is not None
    assert proc["attached_to_id"] == "region:/Users/test/projects/foo"
    assert proc["label"] == "claude (4821)"

    assert len(result["edges"]) == 1
    e = result["edges"][0]
    assert e["source"] == "region:/Users/test/projects/foo"
    assert e["target"] == "process:4821"
    assert e["style"] == "process"


def test_process_cwd_no_match_produces_no_edge():
    """process with unmatched cwd → no edge (orphan process, no home edge)."""
    processes = [{
        "pid": 5555,
        "cmdline": "claude code",
        "cwd": "/tmp",
        "uptime_sec": 60,
    }]
    result = _base(processes=processes)

    proc = _node(result, "process:5555")
    assert proc is not None
    assert proc["attached_to_id"] is None

    assert len(result["edges"]) == 0


def test_severity_high_wins_over_med():
    """two findings on same path: HIGH wins over MED."""
    findings = [
        {"rule": "r1", "severity": "MED", "target": "/Users/test/.claude/CLAUDE.md", "message": "m"},
        {"rule": "r2", "severity": "HIGH", "target": "/Users/test/.claude/CLAUDE.md", "message": "h"},
    ]
    result = _base(claude_files=[CLAUDE_MD_FILE], findings=findings)
    config = _node(result, "config:/Users/test/.claude/CLAUDE.md")
    assert config["severity"] == "HIGH"


def test_severity_string_or_enum_handled():
    """severity as plain string applied to region node."""
    findings = [{"rule": "stale_repo", "severity": "MED", "target": "/Users/test/projects/bar", "message": "stale"}]
    result = _base(repos=[REPO_BAR], findings=findings)
    region = _node(result, "region:/Users/test/projects/bar")
    assert region["severity"] == "MED"


# ---------------------------------------------------------------------------
# New tests
# ---------------------------------------------------------------------------

def test_emits_top_level_regions():
    """region:.claude and region:projects always present with no parent."""
    result = _base()
    claude_r = _node(result, "region:.claude")
    projects_r = _node(result, "region:projects")
    assert claude_r is not None
    assert projects_r is not None
    assert claude_r["parent"] is None
    assert projects_r["parent"] is None


def test_repo_emitted_as_region_under_projects():
    """Repo becomes type=region, parent=region:projects, id=region:<path>."""
    result = _base(repos=[REPO_FOO])
    region = _node(result, "region:/Users/test/projects/foo")
    assert region is not None
    assert region["type"] == "region"
    assert region["parent"] == "region:projects"
    assert region["branch"] == "main"
    assert region["has_process"] is False


def test_landmarks_callable_called_and_results_parented():
    """list_landmarks stub returns one file → config node parented under repo region."""
    landmark = {
        "path": "/Users/test/projects/foo/README.md",
        "name": "README.md",
        "size_bytes": 256,
        "tokens_est": 80,
        "age_days": 3,
        "auto_loaded": False,
    }
    called_with = []
    def stub_landmarks(path):
        called_with.append(path)
        return [landmark] if path == "/Users/test/projects/foo" else []

    result = _base(repos=[REPO_FOO], list_landmarks=stub_landmarks)

    assert "/Users/test/projects/foo" in called_with
    lm_node = _node(result, "config:/Users/test/projects/foo/README.md")
    assert lm_node is not None
    assert lm_node["parent"] == "region:/Users/test/projects/foo"


def test_landmarks_dedup_with_project_md():
    """If landmark scanner already emitted a path, project_md won't duplicate it."""
    shared_path = "/Users/test/projects/foo/CLAUDE.md"
    landmark = {
        "path": shared_path,
        "name": "CLAUDE.md",
        "size_bytes": 512,
        "tokens_est": 200,
        "age_days": 2,
        "auto_loaded": True,
    }
    project_md = [{
        "path": shared_path,
        "name": "CLAUDE.md",
        "size_bytes": 512,
        "tokens_est": 200,
        "age_days": 2,
        "auto_loaded": False,
    }]
    result = _base(repos=[REPO_FOO], project_md=project_md, list_landmarks=lambda _: [landmark])
    config_nodes = [n for n in result["nodes"] if n.get("path") == shared_path]
    assert len(config_nodes) == 1


def test_config_file_in_rules_subdir_parented_under_rules_region():
    """A claude_file under ~/.claude/rules/ → rules region emitted, file parented under it."""
    rules_file = {
        "path": "/Users/test/.claude/rules/workflow.md",
        "name": "workflow.md",
        "size_bytes": 300,
        "tokens_est": 100,
        "age_days": 1,
        "auto_loaded": True,
    }
    result = _base(claude_files=[rules_file])
    rules_region = _node(result, "region:.claude/rules")
    assert rules_region is not None
    assert rules_region["parent"] == "region:.claude"

    f = _node(result, "config:/Users/test/.claude/rules/workflow.md")
    assert f is not None
    assert f["parent"] == "region:.claude/rules"


def test_severity_applies_to_region_node():
    """HIGH finding on a repo path → the region node has severity='HIGH'."""
    findings = [{"rule": "r1", "severity": "HIGH", "target": "/Users/test/projects/foo", "message": "bad"}]
    result = _base(repos=[REPO_FOO], findings=findings)
    region = _node(result, "region:/Users/test/projects/foo")
    assert region["severity"] == "HIGH"


def test_project_md_not_matching_any_repo_parented_under_projects():
    """project_md with no matching repo → parented under region:projects."""
    pm = {
        "path": "/Users/test/projects/orphan/CLAUDE.md",
        "name": "CLAUDE.md",
        "size_bytes": 100,
        "tokens_est": 30,
        "age_days": 1,
        "auto_loaded": False,
    }
    result = _base(project_md=[pm])
    config = _node(result, "config:/Users/test/projects/orphan/CLAUDE.md")
    assert config is not None
    assert config["parent"] == "region:projects"
