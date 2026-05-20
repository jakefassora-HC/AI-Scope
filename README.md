# scope

Read-only local visualizer for Claude Code config, your git portfolio, and your
personal knowledge graph. Catches config rot, stale CLAUDE.md files, abandoned
worktrees, and at-risk unpushed work — and now builds a live graph of the people,
projects, and tools you interact with, without burning Claude tokens to ask.

## Install

```bash
cd ~/projects/scope
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Knowledge graph (optional)

The Knowledge tab works without Neo4j — it reads from SQLite and renders
whatever has been ingested. To enable full Graphiti graph sync:

```bash
docker compose up -d   # starts Neo4j on bolt://localhost:7687
# set env vars (add to .env or export):
# NEO4J_URI=bolt://localhost:7687
# NEO4J_USER=neo4j
# NEO4J_PASSWORD=scopepassword
# OPENAI_API_KEY=<your key>  (required by Graphiti for entity resolution)
```

## Run

```bash
python app.py
```

Open <http://127.0.0.1:8765>.

## What it does

Six tabs:
- **Claude Context** — every CLAUDE.md and `~/.claude/` config file, with token cost
- **File Browser** — click into any folder under `~` (deny list respected)
- **Processes** — running `claude` CLI processes and their working directory
- **Git State** — every repo in `~/projects/` + every active worktree
- **Map** — interactive D3 visualization (Circles ◉ / Sunburst ◐ toggle) of your whole portfolio: repos → phases → plan files. Click any `.md` or `.html` plan file to read it inline.
- **Knowledge** — D3 force graph of entities (people, projects, channels, tools) and their relationships, built from Slack and Miro content via n8n ingestion. Click any node for details. Hit **Sync Graph** to push new episodes to Neo4j.

Plus an **Insights** panel surfacing common config-rot patterns.

### n8n ingestion workflows

`n8n/slack-ingest.json` and `n8n/miro-ingest.json` are importable n8n workflows
that poll Slack channels and Miro boards on a schedule, extract entities with
Claude haiku, and POST structured knowledge to `/api/knowledge/ingest`.

Before importing, replace the `REPLACE_WITH_*` placeholders in each JSON with
your channel/board IDs and n8n credential IDs. Set `ANTHROPIC_API_KEY` in n8n's
environment variables.

## Roadmap status

- **v1 (Claude Context, File Browser, Processes, Git State, Insights):** ✅ shipped — see [PRD.md](PRD.md)
- **v2 (Map tab, System visualization):** ✅ shipped — see [docs/PRD-v2.md](docs/PRD-v2.md)
- **v2.5 (Plan documents + Circles/Sunburst + click-to-read modal):** ✅ shipped — see [docs/PRD-v2.5.md](docs/PRD-v2.5.md)
- **v2.6 (1Hz activity probe + git-aware 3-status phases):** ✅ shipped — see [docs/PRD-v2.6.md](docs/PRD-v2.6.md)
- **v2.7 (commit ↔ phase attribution + phase detail modal):** ✅ shipped — click any phase circle/arc to see its plan files and the commits attributed to it
- **v3 (Knowledge graph — Graphiti + Neo4j + D3 force graph + n8n ingestion):** ✅ shipped — see [docs/superpowers/plans/2026-05-19-knowledge-graph.md](docs/superpowers/plans/2026-05-19-knowledge-graph.md)

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
