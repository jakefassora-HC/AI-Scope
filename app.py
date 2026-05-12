"""scope — Flask entrypoint."""
import os
from pathlib import Path
from flask import Flask, jsonify, render_template, request, abort

from scope.config_scanner import scan_claude_dir, find_claude_md_files
from scope.file_browser import list_dir
from scope.process_scanner import find_claude_processes
from scope.git_scanner import find_repos
from scope.rules import evaluate_all
from scope.tree_builder import build_tree
from scope.plan_scanner import scan_planning, list_plan_files
from scope.activity_scanner import scan_activity
from scope.exclusions import is_excluded
from scope.redact import redact
from scope.commit_mapper import phase_commits

app = Flask(__name__, static_folder="static", template_folder="templates")
HOME = Path.home()

# Hosts we accept Host-header for. Anything else → 403 (DNS rebinding defense).
_ALLOWED_HOSTS = {"127.0.0.1", "127.0.0.1:8765", "localhost", "localhost:8765"}


@app.before_request
def _validate_host():
    """Reject requests whose Host header isn't localhost.

    Mitigates DNS rebinding: a malicious site can resolve attacker.example
    to 127.0.0.1, then make `fetch('http://attacker.example:8765/api/plan')`
    from the user's browser — bypassing same-origin because Origin still
    matches the attacker domain. Strict Host-header allow-listing kills that.
    """
    host = (request.host or "").lower()
    if host not in _ALLOWED_HOSTS:
        abort(403)


@app.after_request
def _no_store(resp):
    """Prevent any caching of scope responses (sensitive local data)."""
    resp.headers["Cache-Control"] = "no-store, private, max-age=0"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp

# Cached set of plan file paths from the last /api/treemap response.
# /api/activity stats these to detect recent edits without rescanning.
_KNOWN_PLAN_PATHS: list[str] = []


def _list_landmarks(repo_path: str) -> list[dict]:
    from os import scandir
    from datetime import datetime, timezone
    from scope.token_estimator import estimate_tokens_from_bytes
    names = {"CLAUDE.md", "README.md", "package.json", "pyproject.toml",
             "Cargo.toml", "go.mod", "requirements.txt"}
    out: list[dict] = []
    try:
        for entry in scandir(repo_path):
            if entry.name not in names or not entry.is_file(follow_symlinks=False):
                continue
            stat = entry.stat(follow_symlinks=False)
            mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            out.append({
                "path": entry.path, "name": entry.name,
                "size_bytes": stat.st_size,
                "tokens_est": estimate_tokens_from_bytes(stat.st_size),
                "modified_iso": mtime.isoformat(timespec="seconds"),
                "age_days": (datetime.now(tz=timezone.utc) - mtime).days,
                "auto_loaded": entry.name == "CLAUDE.md",
            })
    except (OSError, PermissionError):
        pass
    return out


@app.get("/health")
def health():
    return jsonify({"status": "ok", "name": "scope", "version": "0.1.0"})


@app.get("/api/config")
def api_config():
    return jsonify({
        "claude_dir": scan_claude_dir(HOME / ".claude"),
        "project_claude_md": find_claude_md_files(HOME / "projects"),
    })


@app.get("/api/browse")
def api_browse():
    raw = request.args.get("path", str(HOME))
    try:
        items = list_dir(Path(raw))
        return jsonify({"path": raw, "items": items})
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403


@app.get("/api/processes")
def api_processes():
    return jsonify({"processes": find_claude_processes()})


@app.get("/api/git")
def api_git():
    return jsonify({
        "projects": find_repos(HOME / "projects"),
        "worktrees": find_repos(HOME / ".claude" / "worktrees"),
    })


@app.get("/api/insights")
def api_insights():
    claude_files = scan_claude_dir(HOME / ".claude")
    project_md = find_claude_md_files(HOME / "projects")
    repos = find_repos(HOME / "projects")
    worktrees = find_repos(HOME / ".claude" / "worktrees")
    home_is_repo = (HOME / ".git").is_dir()
    findings = evaluate_all(
        config_files=claude_files + project_md,
        repos=repos,
        worktrees=worktrees,
        home_is_git_repo=home_is_repo,
    )
    return jsonify({"findings": findings, "home_is_git_repo": home_is_repo})


@app.get("/api/treemap")
def api_treemap():
    claude_files = scan_claude_dir(HOME / ".claude")
    project_md = find_claude_md_files(HOME / "projects")
    repos = find_repos(HOME / "projects")
    worktrees = find_repos(HOME / ".claude" / "worktrees")
    processes = find_claude_processes()
    home_is_repo = (HOME / ".git").is_dir()
    findings = evaluate_all(
        config_files=claude_files + project_md,
        repos=repos,
        worktrees=worktrees,
        home_is_git_repo=home_is_repo,
    )
    tree = build_tree(
        claude_files=claude_files,
        project_md=project_md,
        repos=repos,
        worktrees=worktrees,
        processes=processes,
        findings=findings,
        home_path=str(HOME),
        list_landmarks=_list_landmarks,
        scan_planning=scan_planning,
        list_plan_files=list_plan_files,
    )
    # Cache plan paths for fast /api/activity probes
    global _KNOWN_PLAN_PATHS
    _KNOWN_PLAN_PATHS = _collect_plan_paths(tree)
    return jsonify(tree)


def _collect_plan_paths(node, out=None):
    if out is None:
        out = []
    if isinstance(node, dict):
        if node.get("kind") == "plan" and node.get("path"):
            out.append(node["path"])
        for c in node.get("children", []) or []:
            _collect_plan_paths(c, out)
    return out


@app.get("/api/activity")
def api_activity():
    """Fast activity probe — poll at 1Hz. Returns claude processes +
    recently-modified plan files (mtime within last 60s)."""
    return jsonify(scan_activity(_KNOWN_PLAN_PATHS))


@app.get("/api/plan")
def api_plan():
    """Return raw content of a plan document.

    Defense layers:
      1. Path must resolve under $HOME.
      2. Path must NOT match the hard-coded deny list (ssh/aws/env/credentials/...).
      3. Extension must be markdown / html / txt.
      4. Size capped at 2 MB.
      5. Content passed through secret redactor before serialization.
    """
    raw = request.args.get("path", "")
    try:
        p = Path(raw).resolve()
        # 1. HOME sandbox
        if HOME.resolve() not in p.parents and p != HOME.resolve():
            return jsonify({"error": "outside HOME"}), 403
        # 2. Deny list — same rules /api/browse enforces
        if is_excluded(p):
            return jsonify({"error": "denied path"}), 403
        if not p.is_file():
            return jsonify({"error": "not a file"}), 404
        # 3. Extension allow-list
        if p.suffix.lower() not in (".md", ".html", ".htm", ".txt"):
            return jsonify({"error": "unsupported file type"}), 400
        # 4. Size cap
        if p.stat().st_size > 2_000_000:
            return jsonify({"error": "too large"}), 413
        # 5. Read + redact secrets before responding
        content = p.read_text(encoding="utf-8", errors="replace")
        return jsonify({
            "path": str(p),
            "ext": p.suffix.lower().lstrip("."),
            "content": redact(content),
        })
    except (OSError, ValueError) as e:
        return jsonify({"error": str(e)}), 400


@app.get("/api/phase-commits")
def api_phase_commits():
    """Return commits attributed to a phase.

    Query params:
      repo:  absolute repo path (must be under HOME, must be a directory)
      phase: phase name as it appears in .planning/phases/<name>/

    Defense layers:
      1. Both repo + phase must resolve under $HOME.
      2. repo must NOT match the deny list.
      3. Phase name is a simple identifier (no slashes, no .. traversal).
    """
    raw_repo = request.args.get("repo", "")
    raw_phase = request.args.get("phase", "")
    if not raw_repo or not raw_phase:
        return jsonify({"error": "repo and phase required"}), 400
    # Phase name must be a single path segment — no traversal possible
    if "/" in raw_phase or ".." in raw_phase or raw_phase.startswith("."):
        return jsonify({"error": "invalid phase name"}), 400
    try:
        repo_p = Path(raw_repo).resolve()
        if HOME.resolve() not in repo_p.parents:
            return jsonify({"error": "outside HOME"}), 403
        if is_excluded(repo_p):
            return jsonify({"error": "denied path"}), 403
        if not repo_p.is_dir():
            return jsonify({"error": "repo not found"}), 404
        phase_dir = repo_p / ".planning" / "phases" / raw_phase
        if not phase_dir.is_dir():
            # Soft-fail: phase might not have a dir but still have commit refs
            phase_dir_str = str(phase_dir)
        else:
            phase_dir_str = str(phase_dir.resolve())
        commits = phase_commits(str(repo_p), phase_dir_str, raw_phase)
        return jsonify({
            "repo": str(repo_p),
            "phase": raw_phase,
            "commits": commits,
        })
    except (OSError, ValueError) as e:
        return jsonify({"error": str(e)}), 400


@app.get("/")
def root():
    return render_template("index.html", home_path=str(HOME))


@app.get("/prototype")
def prototype():
    return render_template("prototype.html", home_path=str(HOME))


if __name__ == "__main__":
    # Debug mode is OFF by default — the Werkzeug debugger console is a remote
    # code execution risk if combined with any Host/CORS bypass. Opt in with
    # SCOPE_DEBUG=1 for local development only.
    debug = os.environ.get("SCOPE_DEBUG") == "1"
    app.run(host="127.0.0.1", port=8765, debug=debug)
