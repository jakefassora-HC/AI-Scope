# scope v2 PRD — "See it" release

**Status:** Draft · 2026-05-12
**Predecessor:** [PRD v1.1](../PRD.md) (shipped 2026-05-12, 14 commits, 49 tests)
**Theme:** One visual that answers "what's the state of my whole Claude Code world?" at a glance.

---

## Goal

Add a **System Map** tab to scope: one interactive node-link diagram that shows config, projects, worktrees, and live Claude processes in one view — with Insights findings overlaid as colored rings on the offending nodes.

v1 surfaces facts per-tab. To see correlations ("which repo is that running `claude` cwd'd into?", "which project's CLAUDE.md is the bloated one?") you click around. The Map collapses that to one picture.

## Non-goals

- Snapshot history / time-series (deferred to v3)
- Open-in-editor button (deferred to v3)
- Ollama / LLM insights (deferred to v3+)
- Editing anything. Map is read-only like the rest of scope.

## Users

Same as v1: solo developers running Claude Code locally who want a quick "am I OK?" view before starting work.

## UX

A 5th tab labeled **Map**, alongside the existing four (Claude Context, File Browser, Processes, Git State). Same dark theme. Same `127.0.0.1:8765` server.

Inside the Map tab:

- **Diagram fills the tab area** (≈ 800×600 viewport on a typical laptop)
- **Layout:** dagre top-down tree. `~ (home)` at the top.
- **Two top-level branches** under `~`: `.claude/` and `projects/`.
- **Children of `.claude/`:** each auto-loaded config file (CLAUDE.md, settings.json, rules/\*.md). Worktrees (`.claude/worktrees/*`) appear as **dashed-edge children of their parent project** when resolvable; otherwise they hang off `.claude/`.
- **Children of `projects/`:** each git repo. Each repo node shows branch + dirty/clean state.
- **Active `claude` processes:** rendered as a **pulsing green badge attached to the node matching the process's cwd**. If cwd matches no node, the process floats off `~`.

### Node decorations

- **Red ring** → node matches a `HIGH` Insights finding
- **Yellow ring** → node matches a `MED` Insights finding
- **Pulsing green dot** → an active `claude` process has this node as its cwd
- **Hover tooltip:** size / branch / age / token count, whichever applies
- **Click a node** → switch to the relevant existing tab and scroll its row into view (Git State for repos, Claude Context for config files, Processes for process nodes)

### Legend

Fixed top-right of the Map tab: a small panel mapping color/ring to meaning. Stays visible while the user pans/zooms.

## Tech

- **Frontend:** [Cytoscape.js](https://js.cytoscape.org/) + [cytoscape-dagre](https://github.com/cytoscape/cytoscape-dagre) loaded via CDN. No build step (consistent with v1's vanilla-JS rule).
- **Backend:** one new route `GET /api/graph` returning `{ nodes: [...], edges: [...] }`. Pure aggregator over existing scanners — **no new scanner modules**. Reuses `scan_claude_dir`, `find_claude_md_files`, `find_repos`, `find_claude_processes`, `evaluate_all`.
- **New file:** `scope/graph_builder.py` — pure-function builder from scanner outputs to graph JSON. Fully unit-testable without Flask.

## Data contract

`GET /api/graph` returns:

```jsonc
{
  "nodes": [
    {
      "id": "home",
      "label": "~",
      "type": "home"
    },
    {
      "id": "config:/Users/x/.claude/CLAUDE.md",
      "label": "CLAUDE.md",
      "type": "config",
      "path": "/Users/x/.claude/CLAUDE.md",
      "size_bytes": 12345,
      "tokens_est": 3086,
      "age_days": 34,
      "severity": "HIGH"        // null | "MED" | "HIGH"
    },
    {
      "id": "repo:/Users/x/projects/foo",
      "label": "foo",
      "type": "repo",
      "path": "/Users/x/projects/foo",
      "branch": "main",
      "dirty": 2,
      "ahead": 0,
      "behind": 0,
      "stale": false,
      "severity": null,
      "has_process": true       // green-dot decoration
    },
    {
      "id": "worktree:/Users/x/.claude/worktrees/foo-fix-x",
      "label": "foo-fix-x",
      "type": "worktree",
      "path": "/Users/x/.claude/worktrees/foo-fix-x",
      "parent_repo_id": "repo:/Users/x/projects/foo",
      "branch": "fix-x",
      "dirty": 0,
      "severity": null
    },
    {
      "id": "process:4821",
      "label": "claude (4821)",
      "type": "process",
      "pid": 4821,
      "cwd": "/Users/x/projects/foo",
      "attached_to_id": "repo:/Users/x/projects/foo"   // or null
    }
  ],
  "edges": [
    { "source": "home", "target": "config:..." },
    { "source": "home", "target": "repo:..." },
    { "source": "repo:...", "target": "worktree:...", "style": "dashed" },
    { "source": "repo:...", "target": "process:4821", "style": "process" }
  ]
}
```

**Severity attribution rule:** a finding's `target` field (already in v1's `/api/insights` output) is matched to a node by absolute path. If multiple findings hit the same node, the highest severity wins.

## Done criteria

1. `pytest tests/ -v` shows all v1 tests still passing plus new `test_graph_builder.py` and `test_api_graph.py`.
2. `python app.py` boots, Map tab renders within ~500 ms on a typical portfolio (≤30 repos).
3. Every node from existing scanners appears in the Map (no silent drops).
4. Red/yellow rings appear on nodes matching Insights findings.
5. Pulsing green dot appears on the repo node matching a running `claude` process's cwd.
6. Clicking a repo node switches to Git State tab AND scrolls the matching row into view.
7. Legend is visible and accurate.
8. No new external HTTP calls. No new network egress. Still 100% local.

## Out of scope (v3+ backlog)

- Snapshot persistence (SQLite) and trend sparklines.
- "Diff since last visit" highlights.
- Open-in-editor button per Insights finding.
- Search/filter inside the Map.
- Local LLM (Ollama) explanations of the graph state.

## Risks

- **Performance on large portfolios.** Mitigation: paginate or collapse `.claude/rules/` if > 10 children. Re-evaluate after first dogfood pass.
- **Cytoscape.js bundle size (~150 KB).** Acceptable — still all local, no build step. We're not optimizing first-load over an internet connection because there isn't one.
- **Process → cwd attribution can be wrong** if a `claude` process is in a non-repo cwd; surface it as a floating node rather than guessing.
