"""scope — Flask entrypoint."""
from pathlib import Path
from flask import Flask, jsonify, render_template, request

from scope.config_scanner import scan_claude_dir, find_claude_md_files
from scope.file_browser import list_dir
from scope.process_scanner import find_claude_processes
from scope.git_scanner import find_repos

app = Flask(__name__, static_folder="static", template_folder="templates")
HOME = Path.home()


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


@app.get("/")
def root():
    return render_template("index.html", home_path=str(HOME))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8765, debug=True)
