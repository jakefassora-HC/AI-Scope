"""Tests for activity_scanner — fast 1Hz probe."""
from __future__ import annotations
import os
import time
from pathlib import Path

from scope.activity_scanner import scan_activity


def test_empty_paths_returns_no_recent(tmp_path):
    out = scan_activity([], recent_window_sec=60)
    assert out["recent_mtimes"] == []
    assert "ts" in out
    assert isinstance(out["processes"], list)


def test_recent_mtime_surfaced(tmp_path):
    f = tmp_path / "PLAN.md"
    f.write_text("hi")
    out = scan_activity([str(f)], recent_window_sec=300)
    paths = [r["path"] for r in out["recent_mtimes"]]
    assert str(f) in paths


def test_old_file_not_surfaced(tmp_path):
    f = tmp_path / "PLAN.md"
    f.write_text("hi")
    # Backdate mtime by 5 minutes
    old = time.time() - 300
    os.utime(str(f), (old, old))
    out = scan_activity([str(f)], recent_window_sec=60)
    assert all(r["path"] != str(f) for r in out["recent_mtimes"])


def test_missing_path_silently_skipped(tmp_path):
    out = scan_activity([str(tmp_path / "does-not-exist.md")], recent_window_sec=60)
    assert out["recent_mtimes"] == []
