"""Smoke tests for autosd CLI commands with deterministic assertions."""

from __future__ import annotations

from typer.testing import CliRunner

from automated_software_developer.cli import app

RUNNER = CliRunner()


def _run(*args: str) -> object:
    return RUNNER.invoke(app, [*args])


def test_help_returns_zero() -> None:
    result = _run("--help")
    assert result.exit_code == 0
    assert "Usage:" in result.stdout


def test_version_returns_zero() -> None:
    result = _run("--version")
    assert result.exit_code == 0
    assert result.stdout.strip()


def test_verify_factory_help_returns_zero() -> None:
    result = _run("verify-factory", "--help")
    assert result.exit_code == 0
    assert "verify-factory" in result.stdout
