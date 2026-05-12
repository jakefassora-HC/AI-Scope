# scope

Read-only local visualizer for Claude Code config and your git portfolio.
Catches config rot, stale CLAUDE.md files, abandoned worktrees, and at-risk
unpushed work — without burning Claude tokens to ask.

## Install

```bash
cd ~/projects/scope
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python app.py
```

Open <http://127.0.0.1:8765>.

## What it does

Five tabs:
- **Claude Context** — every CLAUDE.md and `~/.claude/` config file, with token cost
- **File Browser** — click into any folder under `~` (deny list respected)
- **Processes** — running `claude` CLI processes and their working directory
- **Git State** — every repo in `~/projects/` + every active worktree
- **Map** — interactive D3 visualization (Circles ◉ / Sunburst ◐ toggle) of your whole portfolio: repos → phases → plan files. Click any `.md` or `.html` plan file to read it inline.

Plus an **Insights** panel surfacing common config-rot patterns.

## Roadmap status

- **v1 (Claude Context, File Browser, Processes, Git State, Insights):** ✅ shipped — see [PRD.md](PRD.md)
- **v2 (Map tab, System visualization):** ✅ shipped — see [docs/PRD-v2.md](docs/PRD-v2.md)
- **v2.5 (Plan documents + Circles/Sunburst + click-to-read modal):** ✅ shipped — see [docs/PRD-v2.5.md](docs/PRD-v2.5.md)

## Security

- Read-only. Never modifies your files.
- Localhost-only (`127.0.0.1`). Not reachable from your network.
- Hard deny list (baked into code): session transcripts, credentials, SSH/AWS/GPG keys, `.env` files, `*.pem`, `*.key`.
- Secret regex redaction before any file content reaches the browser.
- No external HTTP calls. No telemetry. No LLM.

## Tests

```bash
pytest tests/ -v
```

## Attributions

Small patterns lifted (with attribution in source headers) from:

- [`phuryn/claude-usage`](https://github.com/phuryn/claude-usage) — MIT — `~/.claude/` scanning patterns
- [`nosarthur/gita`](https://github.com/nosarthur/gita) — MIT — per-repo git status logic
