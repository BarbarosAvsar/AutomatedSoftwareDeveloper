"""Smoke tests for autosd CLI commands with deterministic assertions."""

from __future__ import annotations

import subprocess
import sys


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "automated_software_developer.cli", *args],
        check=False,
        capture_output=True,
        text=True,
    )


def test_help_returns_zero() -> None:
    result = _run("--help")
    assert result.returncode == 0
    assert "Usage:" in result.stdout


def test_version_returns_zero() -> None:
    result = _run("--version")
    assert result.returncode == 0
    assert result.stdout.strip()


def test_verify_factory_help_returns_zero() -> None:
    result = _run("verify-factory", "--help")
    assert result.returncode == 0
    assert "verify-factory" in result.stdout
