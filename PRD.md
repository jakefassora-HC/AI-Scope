# scope — Product Requirements Document

**Status:** ✅ Shipped (v1.1) · 2026-05-12 · 14 commits · 49 tests passing at v1 cut
**Successors:** [v2 PRD](docs/PRD-v2.md) (System Map) → [v2.5 PRD](docs/PRD-v2.5.md) (Plan viewer)
**Owner:** Jake Fassora
**Date:** 2026-05-12

---

## 1. Overview

`scope` is a **read-only local browser app** that visualizes two invisible things on your machine:

1. **What Claude has access to** — every `CLAUDE.md`, every config file, every hook, every MCP server, every rule. Sized, labeled by load behavior (auto-loaded every turn vs. on-demand), with token cost estimates per source.
2. **Your git portfolio state** — every repo on your laptop and every active Claude Code worktree, with branch, ahead/behind, dirty status, and staleness flags.

A built-in **rules engine** annotates findings in plain English ("This CLAUDE.md is 18KB and auto-loaded — costs ~4,700 tokens every turn; consider archiving").

**Why it exists:** Config rot is invisible. You can't see what Claude is loading on every turn until something explodes (slow responses, high token bills, weird behavior tied to a CLAUDE.md you forgot existed). `scope` makes it visible so you catch problems early without burning tokens asking Claude.

**Mental model:** *Google Maps for what's on your machine that Claude reads.*

---

## 2. Users & Use Cases

**Primary user:** A Claude Code power user (non-developer or developer) who wants visibility into their AI tooling without learning to grep configs or interpret JSONL logs.

| Situation | What `scope` shows |
|---|---|
| "Claude keeps mentioning an old project I deleted" | Surfaces the rogue CLAUDE.md still in `~` or a parent directory |
| "Why are my responses slow / token bills high?" | Token cost breakdown per config source per turn |
| "Which agents are running in worktrees right now?" | List of active `~/.claude/worktrees/agent-*` with branch + age |
| "Where is my Claude Code currently running?" | Shows active `claude` processes and their working directory |
| "Which of my repos have unpushed work?" | Multi-repo dashboard with ahead/behind counts |
| "Let me just see what's in this folder" | Click any folder under `~` (deny-list respected) and browse |
| "Should I prune this CLAUDE.md?" | Rules engine surfaces "auto-loaded + stale + large" warnings |

---

## 3. Goals & Non-Goals

### Goals (v1)

- **Read-only.** Never modify any file the user owns.
- **Local-only.** No cloud, no API calls, no telemetry.
- **No AI dependency.** v1 ships without any LLM. Rules engine = deterministic + fast + no install friction.
- **Approachable stack.** Python + Flask + vanilla JS — a non-coder can read the code.
- **Fast first paint.** A scan of `~/.claude/` + `~/projects/` should complete in under 2 seconds on a normal SSD.
- **Plain-English UI.** Every number has a human explanation next to it. Every technical term has a tooltip.

### Non-goals (v1) — explicitly excluded

- ❌ **Ollama or any LLM integration** (deferred to v2)
- ❌ Editing or pruning files automatically
- ❌ Reading session transcripts (`~/.claude/projects/<...>/*.jsonl`)
- ❌ Reading `.credentials.json` or any auth tokens
- ❌ GitHub API integration
- ❌ Diff rendering or stash content viewing
- ❌ A graph view (list/tree only in v1)
- ❌ Real-time SSE streaming of session activity
- ❌ Multi-user, sharing, or any kind of export

### v2 parking lot (deferred)

- Ollama integration for free-form "Analyze with AI" buttons
- GitHub PR / CI status
- Editable pruning workflow (with backup + diff preview)
- Session transcript inspector (with mandatory redaction)
- Graph visualization (CodeBoarding-style)
- Multi-machine portfolio sync

---

## 4. v1 Feature List

### 4.1 Claude Context section

A list/tree view of everything Claude reads:

- **Global**: `~/.claude/CLAUDE.md`, `~/.claude/settings.json`, `~/.claude/rules/*.md`, `~/.claude/memory/`
- **Project-level**: every `CLAUDE.md` found in `~/projects/*/`
- **Per file**: size in bytes, estimated tokens, load behavior badge (`AUTO` / `ON-DEMAND`), last modified date
- **Per file detail panel**: contents preview (first 500 chars, after secret redaction)
- **Summary widget**: total tokens auto-loaded per turn, with context ("about 20% of your response budget")

### 4.2 File Browser section

Click any folder under `~` to walk its contents:

- Tree expansion: click a folder, see its immediate children
- File click: opens a preview (first 500 chars, redacted)
- Deny-list enforced — refuses to walk into excluded paths
- Size + last-modified shown on every entry
- Symlinks not followed

### 4.3 Active Claude Processes section

- Detects running `claude` (Claude Code CLI) processes via `psutil`
- Shows each one's PID, working directory, and how long it's been running
- Empty state: "No Claude processes running"

### 4.4 Git State section

A list view of every git repo in:
- `~/projects/*` — your real projects
- `~/.claude/worktrees/agent-*` — Claude Code agent sandboxes

**Per repo:** path, branch, uncommitted file count, untracked file count, commits ahead/behind remote, stash count, worktree count (with paths), last commit date + relative age, staleness flag.

**No file contents.** Counts and metadata only.

### 4.5 Rules Engine (plain-English insights)

A small set of deterministic rules that surface common config-rot patterns:

| Rule | Triggers when | Severity |
|---|---|---|
| `auto_loaded_and_large` | File auto-loads + > 8KB | High |
| `stale_auto_loaded` | Auto-loads + not edited 30+ days | Medium |
| `home_is_git_repo` | `~/.git` exists | High |
| `orphaned_worktree` | Worktree not touched in 14+ days | Medium |
| `dirty_unpushed_stale` | Repo dirty + ahead of remote + last commit > 7 days | Medium |
| `duplicate_claude_md` | Two CLAUDE.md files with >80% content overlap | Low |

Each rule returns `(severity, plain_english_message)`. New rules can be added without touching the UI.

### 4.6 UI

- Single browser page at `http://127.0.0.1:8765`
- Four tabs: **Claude Context** | **File Browser** | **Processes** | **Git State**
- A top-level **Insights** panel always visible (output of the rules engine)
- Manual refresh button
- No login, no auth, no sessions
- Dark theme by default
- Plain-English captions on every number; tooltips on every technical term

---

## 5. Security & Threat Model

### 5.1 Hard exclusion list (baked into code, non-configurable)

The scanner refuses to walk into or open any path matching:

```
~/.claude/projects/          # session transcripts — never
~/.claude/.credentials.json  # auth tokens — never
~/.ssh/
~/.aws/
~/.gnupg/
~/.config/gh/
**/.env*
**/id_rsa*
**/*.pem
**/*.key
**/*.p12
```

Not a setting. Not a flag. Hard refusal in code.

### 5.2 Network surface

- Flask app binds to `127.0.0.1` only. Never `0.0.0.0`.
- All endpoints `GET`-only.
- No CORS.
- No external HTTP calls at all in v1.

### 5.3 Filesystem safety

- `os.walk(followlinks=False)` everywhere.
- Every resolved path validated to be under `~` before opening.
- File reads size-capped at 256KB per file.

### 5.4 Secret redaction (defense in depth)

Regex pass for: `sk-...`, `ghp_...`, `AKIA...`, JWTs, `xoxb-...`, AWS secret keys, generic 32+ char high-entropy hex. Matches → `[REDACTED]`.

### 5.5 Process detection privacy

- `psutil` reads only `cmdline` and `cwd` of `claude` processes.
- We never read the memory or open files of other processes.
- If a non-Claude process happens to be named `claude`, we still only show its cwd — same as any process viewer would.

### 5.6 Logging

- Logs path + status code only.
- **Never logs file contents.**
- Log file at `~/projects/scope/scope.log`, rotated daily, gitignored.

---

## 6. Architecture

### 6.1 Stack

```
Python 3.11+
├── Flask 3.x              HTTP server, templating
├── GitPython 3.x          git status scanning
├── psutil 5.x             process detection
├── tiktoken               Token estimation
└── vanilla JS + CSS       Browser UI, no build step
```

No npm. No TypeScript. No bundler. No framework. **No LLM dependency.**

### 6.2 Component diagram

```
[Browser at 127.0.0.1:8765]
         ↓ GET /
[Flask app.py]
         ↓
[scope/ package]
  ├─ config_scanner.py   → walks ~/.claude/ + finds CLAUDE.md files
  ├─ git_scanner.py      → runs git status per repo
  ├─ file_browser.py     → on-demand directory walker
  ├─ process_scanner.py  → finds running claude processes
  ├─ rules.py            → deterministic insight rules
  ├─ token_estimator.py  → byte/char → rough token count
  ├─ exclusions.py       → hard deny list
  └─ redact.py           → regex secret masking
         ↓
[Filesystem: ~/.claude/, ~/projects/, ~/]
```

### 6.3 Project layout

```
~/projects/scope/
├── README.md
├── PRD.md
├── PLAN.md                   ← implementation plan (next deliverable)
├── docs/
│   ├── PRD.html              ← human-readable PRD render
│   └── PLAN.html             ← human-readable plan render
├── .gitignore
├── requirements.txt
├── app.py                    ← Flask entrypoint
├── scope/
│   ├── __init__.py
│   ├── config_scanner.py
│   ├── git_scanner.py
│   ├── file_browser.py
│   ├── process_scanner.py
│   ├── rules.py
│   ├── token_estimator.py
│   ├── exclusions.py
│   └── redact.py
├── templates/
│   └── index.html
├── static/
│   ├── style.css
│   └── app.js
└── tests/
    ├── test_exclusions.py
    ├── test_redact.py
    └── test_rules.py
```

---

## 7. Build Phases

Six small phases, each independently verifiable.

| Phase | What | Time |
|---|---|---|
| 0 | Scaffold (dir layout, requirements.txt, Flask hello-world, git init) | 30 min |
| 1 | Config scanner + deny list + redact (with tests) | 1–2 hrs |
| 2 | CLAUDE.md hierarchy + token budget widget + plain-English UI | 2 hrs |
| 3 | File browser + process scanner | 1.5 hrs |
| 4 | Git portfolio scanner | 2–3 hrs |
| 5 | Rules engine + Insights panel + polish | 1.5 hrs |

**Total estimated effort:** 7–10 hours of focused work.

Detailed task breakdown lives in `PLAN.md` (next deliverable).

---

## 8. Inspiration & Attributions

We are **not forking** any of these. We take small, well-cited patterns from MIT-licensed projects:

| Source | What we lift | License |
|---|---|---|
| [`phuryn/claude-usage`](https://github.com/phuryn/claude-usage) | `~/.claude/` directory scanning patterns, Flask scaffold | MIT |
| [`nosarthur/gita`](https://github.com/nosarthur/gita) | Per-repo `git status` computation logic | MIT |

(CodeBoarding's Ollama wrapper is no longer relevant for v1 — deferred with Ollama.)

All attributions live in `README.md` and source headers of the relevant files.

---

## 9. Open Questions

| Question | Default if no decision |
|---|---|
| Default port? | `8765` (memorable, low collision) |
| Should we scan `~/projects/archive/`? | No — exclude `archive/` subdirs by default |
| What's "stale" for a worktree? | 14 days since last activity |
| What's "stale" for a CLAUDE.md? | 30 days since last edit |

---

## 10. Success Criteria

`scope` v1 ships when all five are true:

1. Opening `localhost:8765` shows every CLAUDE.md and config file under `~/.claude/` and `~/projects/`, with token cost per file in plain English.
2. The Git State tab lists every repo and every worktree with accurate branch + dirty + ahead/behind data.
3. The Processes tab shows any running `claude` Code processes (or "none running" cleanly).
4. The File Browser walks any folder under `~` on demand, respecting the deny list (verified by unit test).
5. The scanner refuses to enter `~/.claude/projects/`, `~/.ssh/`, `~/.aws/`, etc. (verified by unit test).
6. The Insights panel surfaces at least one real, actionable finding on Jake's actual machine.

---

*End of PRD v1.1.*
