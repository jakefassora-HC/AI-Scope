# scope v2.6 PRD — "Real-time + Real progress"

**Status:** ✅ Shipped · 2026-05-12 · PR #6
**Predecessor:** [v2.5 PRD](PRD-v2.5.md) (plan viewer + circle packing + sunburst)
**Theme:** Show *where AI agents are working right now* (live), and let *git history* drive a more honest "done" signal than file-presence heuristics.

---

## Problem

Two gaps after v2.5 dogfooding:

1. **The Map is too slow to be live.** Auto-refresh is 10s but the user wants ~1s so they can *see* an agent moving between files. Polling the full tree at 1Hz costs ~5.7 s per scan (measured) — would saturate a core.
2. **Phase status is over-confident.** Current rule: `*-VERIFICATION.md` exists → status = `complete`. That's a doc-presence heuristic. A phase can have VERIFICATION.md and zero shipping commits. Or have implementation commits but never get a VERIFICATION.md written. The map lies about progress in both directions.

## Goals

1. **1-second activity refresh** without the 5.7 s tree scan tax.
2. **Git-aware phase status** — derive a richer status taxonomy from commits / merges / branch state, not just file existence.
3. **Stay local-only.** No GitHub API calls in v2.6 (optional v2.7).

## Non-goals

- Editing plans or commits (still read-only — same as every v).
- Cross-repo activity timeline (deferred — would need event log persistence).
- GitHub PR status via API (deferred to v2.7, opt-in only).
- Sub-second polling (1s is fine; faster = noise).

---

## Design

### Part A: Activity polling — split slow + fast

**Two endpoints, two cadences:**

| Endpoint | Cost | Cadence | What it returns |
|---|---|---|---|
| `/api/treemap` (existing) | ~5.7s | **30s** (raised from 10s) or on-demand via refresh button | Full tree: repos, plans, phases, git state, severity |
| `/api/activity` (**new**) | <100 ms | **1s** while Map is active | Just *what changed*: active claude processes, their open files, recently-touched plan paths |

`/api/activity` shape:

```jsonc
{
  "ts": 1715520000,
  "processes": [
    { "pid": 4821, "cwd": "/Users/x/projects/foo", "open_plans": ["..."] }
  ],
  "recent_mtimes": [
    { "path": "/Users/x/projects/foo/.planning/phases/06/06-PLAN.md", "mtime": 1715519995 }
  ]
}
```

`recent_mtimes` is the *clever* part: walk only the planning dirs (already known from the last tree scan), stat each plan file, return files modified within the last `60s`. Caches the path list in memory so it's a flat stat-loop, no recursion per tick.

### Frontend overlay

When `/api/activity` arrives:

- Loop the cached tree, set `claude_active` on each leaf whose path is in `processes[].open_plans` → orange glow
- Set `recently_modified` on each leaf in `recent_mtimes[]` → blue pulse animation (decays after 5s)
- **No re-layout.** Pure SVG attr update on existing circles/arcs. Zoom state preserved.

The full tree poll continues at 30s — that's when new repos / new plan files appear. Most users sit at the same view for minutes, so the heavier scan happens 2-3 times per session.

### Refresh indicator

Two-part: a fast tick (1s) and a slow rebuild timestamp (30s). Small text in the toolbar so user knows both clocks are alive.

### Cost budget

- 1Hz × ~100ms = 10% of one core. Acceptable.
- Battery: psutil call per second is cheap; macOS power impact negligible at this rate.
- If user closes the tab or backgrounds the window, both polls pause (existing `document.hidden` guard).

---

### Part B: Git-aware phase status

Today's rule (file presence → status) is wrong in two ways. Adding git brings four new signals:

| Signal | Where it comes from | What it tells us |
|---|---|---|
| `last_commit_at` | `git log -1 --format=%ct -- <phase-dir>` | When was anything in the phase last touched in a commit |
| `commit_count` | `git log --oneline -- <phase-dir> \| wc -l` | How much work has been *recorded*, not just planned |
| `referenced_in_commits` | `git log --grep="<phase-name>"` count | How many commits *outside* the phase dir reference the phase (the actual implementation work) |
| `merged_to_main` | check if `feat/<phase>` or similar branch merged into main | The work shipped |

**New taxonomy** (KISS — 3 statuses, locked):

| Status | Rule | Color |
|---|---|---|
| `done` | VERIFICATION.md exists AND (referenced_in_commits ≥ 1 OR commit_count ≥ 1) | green |
| `active` | claude_active on any file OR commits within last 7d OR has PLAN.md with recent edits | blue |
| `idle` | everything else — has plan/research/discuss but no recent activity; or empty draft | gray |

Strong signal: `done` requires *both* a verification artifact and shipping commits — a written-but-unshipped phase falls back to `idle`, surfacing work that needs to actually land. `active` collapses all "in-flight" states. `idle` is the catch-all that flags phases worth revisiting.

(Earlier draft proposed 6 statuses; pushed back as too many. KISS rule applied.)

### Implementation

- New `scope/git_phase_scanner.py`:
  - `phase_git_signals(repo_path, phase_dir) -> dict`
  - One subprocess per phase, in parallel (process pool). Worst case ~50 git calls; bounded.
- `plan_scanner.scan_planning()` enriches each phase dict with these signals.
- `tree_builder._phase_status()` becomes the new taxonomy above.
- Frontend legend updates: 6 statuses, distinct colors.

### Caching

`git log` over a phase dir is fast (<10ms per call) but 50 phases × 8 repos = 400 calls. Memoize the result per `(repo_HEAD, phase_dir)` so subsequent /api/treemap calls within the same git HEAD reuse cached values. Invalidate on HEAD change (cheap to detect).

---

## Done criteria

1. ✅ `/api/activity` returns in <100ms (p95)
2. ✅ Frontend polls `/api/activity` every 1s; `/api/treemap` every 30s; both pause on tab hide
3. ✅ Plan-leaf `claude_active` flips orange/clear within 1s of a process opening/closing a file
4. ✅ Each phase carries `last_commit_at`, `commit_count`, `referenced_in_commits`, `merged_to_main` in the API
5. ✅ Map shows 6 statuses (shipped / complete / active / stalled / planning / draft) with distinct colors
6. ✅ Legend updated to match
7. ✅ Tooltip on a phase shows the relevant git stats ("last commit 2d ago · 12 commits referencing this phase · shipped on `main`")
8. ✅ Per-phase git scan cached on HEAD; invalidated correctly on new commits
9. ✅ No new external network egress (still local-only)
10. ✅ All tests passing including new `test_git_phase_scanner.py`

## Risks

- **`git log --grep` false positives.** A phase named `01-auth` matches commits about "author". Mitigation: require a stronger pattern (phase number prefix + dash, e.g. `01-` or `phase 01`), or look for the literal phase dir name.
- **Worktree edge case.** A phase's "referenced_in_commits" should count commits on the project's main repo, not the worktree. Resolve by always running `git log` from the parent repo path, not the worktree.
- **Slow first tree-load on large monorepos.** 50+ phases × 4 git calls each = 200 subprocess invocations. Mitigation: parallel pool + cache. If still slow, fall back to file-presence rule and mark the phase `(git stats pending)`.
- **`merged_to_main` detection is heuristic.** No formal phase→branch mapping. Best-effort: look for branches named `feat/<phase>`, `feature/<phase-number>`, etc., AND look for the branch in `git branch --merged main`.

## Out of scope (v2.7+)

- **GitHub API integration** for real PR status. Would require `gh` CLI auth or a token. Opt-in flag, off by default.
- **Activity timeline** across repos ("today claude touched: a, b, c").
- **Commit graph mini-view** per phase ("see the 12 commits that implemented this phase").
- **Cross-machine sync** — none of this leaves localhost in v2.x.

---

## Open questions for Jake

1. **Cadence:** does **1s activity / 30s tree** feel right, or do you want activity even faster (500ms)? My take: 1s is plenty — the human eye doesn't perceive 500ms vs 1s file-switching latency.
2. **Status taxonomy:** is **6 statuses** too many, or do you want `stalled` and `complete` rolled together? My take: keep all 6 — `stalled` is the most useful one because it surfaces work you forgot about.
3. **GitHub PR status:** ship in v2.6 or punt to v2.7? My take: **punt**. Local git gives 90% of the value, GitHub needs auth + breaks the local-only principle. Add later as an opt-in.
4. **Cache:** memoize git-scan results across requests? Slight complexity, big speed win. My take: yes, by `(repo, HEAD-sha, phase-dir)`.
