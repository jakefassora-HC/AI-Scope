"""scope — Flask entrypoint."""
from pathlib import Path
from flask import Flask, jsonify, render_template, request

from scope.config_scanner import scan_claude_dir, find_claude_md_files
from scope.file_browser import list_dir
from scope.process_scanner import find_claude_processes
from scope.git_scanner import find_repos
from scope.rules import evaluate_all
from scope.tree_builder import build_tree
from scope.plan_scanner import scan_planning, list_plan_files

app = Flask(__name__, static_folder="static", template_folder="templates")
HOME = Path.home()


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
    return jsonify(build_tree(
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
    ))


@app.get("/api/plan")
def api_plan():
    """Return raw content of a plan document. Sandbox to HOME."""
    raw = request.args.get("path", "")
    try:
        p = Path(raw).resolve()
        if HOME.resolve() not in p.parents and p != HOME.resolve():
            return jsonify({"error": "outside HOME"}), 403
        if not p.is_file():
            return jsonify({"error": "not a file"}), 404
        if p.suffix.lower() not in (".md", ".html", ".htm", ".txt"):
            return jsonify({"error": "unsupported file type"}), 400
        if p.stat().st_size > 2_000_000:
            return jsonify({"error": "too large"}), 413
        return jsonify({
            "path": str(p),
            "ext": p.suffix.lower().lstrip("."),
            "content": p.read_text(encoding="utf-8", errors="replace"),
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
    app.run(host="127.0.0.1", port=8765, debug=True)
