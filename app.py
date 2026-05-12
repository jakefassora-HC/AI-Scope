"""scope — Flask entrypoint."""
from pathlib import Path
from flask import Flask, jsonify, render_template

from scope.config_scanner import scan_claude_dir, find_claude_md_files

app = Flask(__name__, static_folder="static", template_folder="templates")

HOME = Path.home()


@app.get("/health")
def health():
    return jsonify({"status": "ok", "name": "scope", "version": "0.1.0"})


@app.get("/api/config")
def api_config():
    """Returns Claude config files + CLAUDE.md hierarchy."""
    claude_files = scan_claude_dir(HOME / ".claude")
    project_claude_md = find_claude_md_files(HOME / "projects")
    return jsonify({
        "claude_dir": claude_files,
        "project_claude_md": project_claude_md,
    })


@app.get("/")
def root():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8765, debug=True)
