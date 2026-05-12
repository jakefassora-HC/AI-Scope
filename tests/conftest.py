"""Shared pytest fixtures."""
import pytest
from pathlib import Path


@pytest.fixture
def fake_home(tmp_path: Path) -> Path:
    """Create a fake home dir layout for testing scanners."""
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "CLAUDE.md").write_text("# Global prefs\n")
    (tmp_path / ".claude" / "settings.json").write_text('{"theme":"dark"}')
    (tmp_path / ".claude" / "projects").mkdir()
    (tmp_path / ".claude" / "projects" / "session.jsonl").write_text("SECRET-TRANSCRIPT")

    (tmp_path / "projects" / "foo").mkdir(parents=True)
    (tmp_path / "projects" / "foo" / "CLAUDE.md").write_text("# Foo project\n" * 100)

    (tmp_path / ".ssh").mkdir()
    (tmp_path / ".ssh" / "id_rsa").write_text("SECRET-KEY")

    return tmp_path
