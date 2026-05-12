"""Tests for scope.file_browser."""
from pathlib import Path
import pytest
from scope.file_browser import list_dir


def test_list_dir_returns_children(fake_home: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(fake_home))
    items = list_dir(fake_home)
    names = [i["name"] for i in items]
    assert ".claude" in names
    assert "projects" in names


def test_list_dir_marks_dirs_and_files(fake_home: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(fake_home))
    items = list_dir(fake_home / "projects" / "foo")
    md = next(i for i in items if i["name"] == "CLAUDE.md")
    assert md["is_dir"] is False
    assert md["size_bytes"] > 0


def test_list_dir_refuses_excluded(fake_home: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(fake_home))
    with pytest.raises(PermissionError):
        list_dir(fake_home / ".ssh")


def test_list_dir_refuses_above_home(fake_home: Path, monkeypatch):
    # Even if asked to list /, must refuse if it's not under HOME.
    monkeypatch.setenv("HOME", str(fake_home))
    with pytest.raises(PermissionError):
        list_dir(Path("/etc"))
