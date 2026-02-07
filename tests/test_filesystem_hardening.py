"""Filesystem hardening tests for path traversal protections."""

from __future__ import annotations

from pathlib import Path

import pytest

from automated_software_developer.agent.security import SecurityError, ensure_safe_relative_path


def test_ensure_safe_relative_path_allows_within_workspace(tmp_path: Path) -> None:
    safe_path = ensure_safe_relative_path(tmp_path, "nested/file.txt")
    assert safe_path == (tmp_path / "nested" / "file.txt").resolve()


def test_ensure_safe_relative_path_blocks_root_reference(tmp_path: Path) -> None:
    with pytest.raises(SecurityError):
        ensure_safe_relative_path(tmp_path, ".")


def test_ensure_safe_relative_path_blocks_traversal(tmp_path: Path) -> None:
    with pytest.raises(SecurityError):
        ensure_safe_relative_path(tmp_path, "../escape.txt")
