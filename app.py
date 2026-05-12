"""scope — Flask entrypoint."""
from flask import Flask, jsonify

app = Flask(__name__, static_folder="static", template_folder="templates")


@app.get("/health")
def health():
    return jsonify({"status": "ok", "name": "scope", "version": "0.1.0"})


@app.get("/")
def root():
    return "<h1>scope is alive</h1><p>Visit /health for status.</p>"


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8765, debug=True)
