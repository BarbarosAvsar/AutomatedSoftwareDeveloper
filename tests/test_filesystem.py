"""File workspace unit tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from automated_software_developer.agent.filesystem import FileWorkspace
from automated_software_developer.agent.security import SecurityError


def test_write_and_read_file(tmp_path: Path) -> None:
    workspace = FileWorkspace(tmp_path)
    workspace.ensure_exists()
    workspace.write_file("pkg/module.py", "value = 1\n")
    assert workspace.read_file("pkg/module.py") == "value = 1\n"
    assert "pkg/module.py" in workspace.changed_files


def test_delete_file(tmp_path: Path) -> None:
    workspace = FileWorkspace(tmp_path)
    workspace.ensure_exists()
    workspace.write_file("temp.txt", "data")
    workspace.delete_file("temp.txt")
    assert not (tmp_path / "temp.txt").exists()


def test_read_optional_returns_none_for_missing_file(tmp_path: Path) -> None:
    workspace = FileWorkspace(tmp_path)
    workspace.ensure_exists()
    assert workspace.read_optional("missing.txt") is None


def test_write_file_blocks_escape(tmp_path: Path) -> None:
    workspace = FileWorkspace(tmp_path)
    workspace.ensure_exists()
    with pytest.raises(SecurityError):
        workspace.write_file("../escape.txt", "bad")
