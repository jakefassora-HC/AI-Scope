"""Security regression tests — covers the v2.6 audit fixes."""
from __future__ import annotations
import os
from pathlib import Path
import pytest

from app import app


@pytest.fixture
def client():
    return app.test_client()


# ── H1: Host header validation (DNS rebinding defense) ───────────────────────

def test_rejects_non_localhost_host(client):
    r = client.get("/api/treemap", headers={"Host": "evil.example.com"})
    assert r.status_code == 403


def test_allows_127_0_0_1_host(client):
    r = client.get("/health", headers={"Host": "127.0.0.1:8765"})
    assert r.status_code == 200


def test_allows_localhost_host(client):
    r = client.get("/health", headers={"Host": "localhost"})
    assert r.status_code == 200


# ── M2: no-store cache header ────────────────────────────────────────────────

def test_no_store_cache_header(client):
    r = client.get("/health")
    assert "no-store" in r.headers.get("Cache-Control", "")


def test_no_sniff_header(client):
    r = client.get("/health")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"


# ── C2: /api/plan deny-list enforcement ──────────────────────────────────────

def test_plan_rejects_outside_home(client):
    r = client.get("/api/plan?path=/etc/passwd")
    assert r.status_code == 403


def test_plan_rejects_ssh_dir(client, tmp_path, monkeypatch):
    """A markdown file inside a deny-listed dir must be refused."""
    # Build a fake HOME with a .ssh subdir holding a .md
    fake_home = tmp_path
    ssh = fake_home / ".ssh"
    ssh.mkdir()
    secret = ssh / "notes.md"
    secret.write_text("very secret")
    monkeypatch.setattr("app.HOME", fake_home)
    r = client.get(f"/api/plan?path={secret}")
    assert r.status_code == 403
    assert "denied" in r.get_json().get("error", "").lower()


def test_plan_rejects_env_file(client, tmp_path, monkeypatch):
    fake_home = tmp_path
    env = fake_home / ".env"
    env.write_text("SECRET=abc")
    monkeypatch.setattr("app.HOME", fake_home)
    # extension is wrong anyway, but the deny list should also fire
    r = client.get(f"/api/plan?path={env}")
    assert r.status_code in (400, 403)


# ── M1: redact() applied to plan content ─────────────────────────────────────

def test_plan_redacts_anthropic_key(client, tmp_path, monkeypatch):
    fake_home = tmp_path
    plan = fake_home / "PLAN.md"
    plan.write_text("API key: sk-ant-1234567890abcdefghijklmnop\nDone.")
    monkeypatch.setattr("app.HOME", fake_home)
    r = client.get(f"/api/plan?path={plan}")
    assert r.status_code == 200
    body = r.get_json()["content"]
    assert "sk-ant-" not in body
    assert "[REDACTED]" in body


def test_plan_redacts_github_pat(client, tmp_path, monkeypatch):
    fake_home = tmp_path
    plan = fake_home / "PLAN.md"
    plan.write_text("token: ghp_1234567890abcdefghijklmnop")
    monkeypatch.setattr("app.HOME", fake_home)
    r = client.get(f"/api/plan?path={plan}")
    assert "[REDACTED]" in r.get_json()["content"]


# ── /api/plan happy path still works ─────────────────────────────────────────

def test_plan_serves_normal_md(client, tmp_path, monkeypatch):
    fake_home = tmp_path
    plan = fake_home / "PLAN.md"
    plan.write_text("# hello\nworld")
    monkeypatch.setattr("app.HOME", fake_home)
    r = client.get(f"/api/plan?path={plan}")
    assert r.status_code == 200
    body = r.get_json()
    assert body["ext"] == "md"
    assert "world" in body["content"]
