"""Tests for scope.process_scanner — uses psutil mocks."""
from unittest.mock import MagicMock, patch
from scope.process_scanner import find_claude_processes


def _make_proc(pid, name, cmdline, cwd, create_time=1700000000.0):
    p = MagicMock()
    p.info = {"pid": pid, "name": name, "cmdline": cmdline,
              "cwd": cwd, "create_time": create_time}
    return p


@patch("scope.process_scanner.psutil.process_iter")
def test_finds_claude_process(mock_iter):
    mock_iter.return_value = [
        _make_proc(101, "claude", ["claude"], "/Users/foo/projects/x"),
        _make_proc(102, "python", ["python", "app.py"], "/Users/foo"),
    ]
    results = find_claude_processes()
    assert len(results) == 1
    assert results[0]["pid"] == 101
    assert results[0]["cwd"] == "/Users/foo/projects/x"


@patch("scope.process_scanner.psutil.process_iter")
def test_empty_when_no_claude(mock_iter):
    mock_iter.return_value = [_make_proc(102, "python", ["python"], "/tmp")]
    assert find_claude_processes() == []


@patch("scope.process_scanner.psutil.process_iter")
def test_handles_access_denied(mock_iter):
    import psutil
    bad = MagicMock()
    bad.info = MagicMock(side_effect=psutil.AccessDenied)
    type(bad).info = property(lambda self: (_ for _ in ()).throw(psutil.AccessDenied()))
    mock_iter.return_value = [bad]
    # Should not crash.
    assert find_claude_processes() == []
