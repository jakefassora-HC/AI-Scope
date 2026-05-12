# scope v2.5 PRD — "Read it" release

**Status:** ✅ Shipped · 2026-05-12 · PR #6 (`feat/v2.5-region-map`)
**Predecessor:** [v2 PRD](PRD-v2.md) (System Map)
**Theme:** Make the Map *useful*. Surface the actual planning documents, and let users read them without leaving the page.

---

## Why v2.5

v2 shipped a System Map but it surfaced files generically: CLAUDE.md, README.md, package.json. Those are "what Claude reads," not "what the user reads." The artifacts users actually care about are the **planning documents** — `PLAN.md`, `PRD.md`, `ROADMAP.md`, `STATE.md`, and GSD phase markdown — and they wanted to *read* those, not just know they exist.

Three concurrent problems also surfaced in v2 dogfooding:
1. The compound-region renderer (cytoscape + fcose) overlapped labels into an unreadable pile for portfolios of 5+ repos.
2. The Map didn't reflect *progress* — a complete phase looked the same as a draft one.
3. Plan files were second-class: you could see *that* they existed, but not *what they said*.

## Goal

Three things, all in the existing Map tab, no new tabs:

1. **Plans as first-class data.** Walk every planning-like folder (`.planning/`, `plans/`, `planning/`, `docs/`, `.gsd/`) plus top-level root docs, capture every `.md` and `.html` file, attach phase + status context where applicable.
2. **A visualization that scales.** Replace the cramped compound-region treemap with D3 zoomable circle packing **and** D3 zoomable sunburst as toggleable views.
3. **Click-to-read.** Clicking any plan file (in either view) opens an in-page modal that renders the markdown — no editor jump, no terminal, no `cat`.

## Non-goals

- Editing plans (still read-only — same boundary as v1 + v2).
- AI summarization of plans (deferred to v3+).
- Snapshot history of plan progress (deferred).
- Sankey, kanban-card, or any other view in the main Map tab (kept in `/prototype` for design reference, not shipped to the production Map).

## Users

Same as v1/v2: solo developers running Claude Code with GSD-style planning workflows.

## UX

**Map tab layout:**
- Top toolbar: view toggle (`◉ Circles` / `◐ Sunburst`) + color legend (complete / iterating / planning / dirty / claude running / HIGH)
- Canvas: 680px tall, centered viewBox so the visualization fills the frame
- Bottom hint: "Click a circle/arc to zoom in · click background or center to zoom out · click any plan file to read it"

**Circle packing:**
- Bubbles sized by content (file bytes, plan counts)
- Centered viewBox so the root packs around the SVG center (fixes the v2.5-α top-left bug)
- Square layout — circles never stretch
- Labels resize and truncate to fit each circle's radius at the current zoom
- Click a leaf plan → open modal · click a branch → zoom in · click background → zoom up one level
- Center text shows current focus + "click background to zoom out" hint

**Sunburst:**
- Capped to **3 rings of visible depth** from the current focus — no more 5-ring spaghetti
- Arcs hidden when too thin to read; labels truncated to available arc-length
- Click a sector to refocus (it becomes the new center)
- Click the center circle to zoom out one level
- Leaf plan-file clicks open the modal directly

**Plan viewer modal:**
- Click any `.md` / `.html` file (in either view) opens a centered modal at min(960px, 92vw) × min(80vh, 820px)
- Markdown rendered via `marked@12` (CDN); HTML rendered raw; truncated/escaped for unknown types
- Themed to match scope (dark, monospace headers, accent-colored h2 underlines)
- Esc or background-click to dismiss

## Tech

- **Frontend:** D3 v7 (`d3-hierarchy`, `d3-shape.arc`, `d3-interpolate.interpolateZoom`) + `marked@12` for markdown. All loaded from `cdn.jsdelivr.net` at first paint, cached by the browser thereafter. **Cytoscape and cytoscape-fcose are removed.**
- **Backend:**
  - New `scope/plan_scanner.list_plan_files(repo_path)` — recursive `.md` / `.html` walk of planning-like dirs, capped at depth 4, with phase + phase_status inheritance from `.planning/phases/<name>/`.
  - Existing `scope/tree_builder.build_tree()` now emits one `plans · <milestone> · <pct>%` group per repo, containing phase subgroups (each with its actual md/html files as leaves) + loose top-level docs.
  - New `GET /api/plan?path=…` — returns `{path, ext, content}` for a single plan file. **HOME-sandboxed** (rejects paths outside `~`), 2 MB cap, only `.md` / `.html` / `.htm` / `.txt` allowed.
- **Tests:** `tests/test_tree_builder.py` updated for new shape; legacy `test_graph_builder.py` kept (route still exists for back-compat).

## Data shape — `GET /api/treemap` (existing route, expanded payload)

```jsonc
{
  "name": "~", "kind": "root", "path": "/Users/x",
  "children": [
    { "name": ".claude", "kind": "region", "subtitle": "global config · auto-loaded each turn",
      "children": [ /* config files as { kind:"file", … } */ ] },
    { "name": "projects", "kind": "region",
      "children": [
        { "name": "human-road-warrior", "kind": "repo",
          "branch": "main", "dirty": 0, "ahead": 0, "behind": 0, "stale": false,
          "has_process": false, "severity": null,
          "children": [
            { "name": "plans · v1.0 · 86%", "kind": "group",
              "milestone": "v1.0", "percent": 86,
              "completed_phases": 5, "total_phases": 7, "file_count": 54,
              "children": [
                /* loose top-level docs first */
                { "name": "CLAUDE.md", "kind": "plan", "path": "...", "ext": "md",
                  "size_bytes": 1234, "tokens_est": 309, "phase": null },
                /* then phase subgroups */
                { "name": "01-contracts-schema-utilities", "kind": "phase", "status": "complete",
                  "children": [
                    { "name": "01-01-PLAN.md", "kind": "plan", "path": "...",
                      "phase": "01-contracts-schema-utilities", "phase_status": "complete" }
                  ]
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

## Done criteria

1. ✅ Every `.md` / `.html` file in any planning-like folder appears as a clickable leaf in the Map.
2. ✅ Each phase carries a status derived from file presence (`*-VERIFICATION.md` → complete, `*-PLAN.md` → iterating, `DISCUSS/RESEARCH.md` only → planning, else → draft).
3. ✅ Color drives status: green = complete, blue = iterating, purple = planning, gray = draft. Repo decorations: green glow = running claude, amber dashed = dirty, red border = HIGH finding.
4. ✅ Clicking a `.md` leaf renders it inline; the user never leaves the page.
5. ✅ Toggle button switches between Circles and Sunburst without refetching `/api/treemap`.
6. ✅ Sunburst limits to 3 visible rings so no portfolio overwhelms the layout.
7. ✅ Circle packing renders centered (the v2-α top-left bug is fixed).
8. ✅ No new external HTTP egress beyond CDN-cached vendor JS.
9. ✅ All 76 tests passing (49 v1 + 12 v2 + 8 v2.5 tree + 7 misc).

## Implementation notes

- **A `/prototype` route** ships alongside `/` for design iteration. It hosts four alternative visualizations (Cards / Circles / Sunburst / Sankey) over the same `/api/treemap` data. Not linked from the main UI; intended for product/design review.
- **`/api/graph` (v2 legacy)** is kept on the server with its tests, but no longer used by any frontend. Candidate for removal once the v2.5 surface is stable.

## Out of scope (v3+ backlog)

- Plan editing / open-in-editor (deferred)
- Snapshot history & diff-since-last-visit
- AI summarization of plans
- Cross-project plan search
- Sankey/kanban as production views (kept in `/prototype` only)
- "Plans rendered as HTML" pipeline (user mentioned this is the long-term direction — handle when GSD/Claude start emitting HTML plans natively)

## Risks

- **HTML plan content can run scripts when rendered raw.** Today `/api/plan` returns HTML untouched; if a plan ships hostile inline JS, it executes in the modal. Acceptable for v2.5 (all plans are written by the user themselves), but worth sandboxing (iframe + `sandbox=""`) before scope ever accepts plans from a third party.
- **D3 + marked CDN bundles (~250 KB total).** First-load cost; cached after. No build step kept the simplicity contract from v1.
- **Plan file walks on huge `docs/` trees** can be slow. Capped at depth 4; if scans regress, add a per-repo file cap.
