"""Documentation parity checks for command inventory snippets."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from automated_software_developer.cli import app

EXPECTED_CORE_COMMANDS = [
    "run",
    "verify-factory",
    "deploy",
    "rollback",
    "promote",
    "release",
    "daemon",
    "telemetry",
    "preauth",
    "policy",
]


def test_readme_core_commands_cover_key_cli_inventory() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0

    readme = Path("README.md").read_text(encoding="utf-8")
    for command in EXPECTED_CORE_COMMANDS:
        assert command in result.stdout
        assert f"autosd {command}" in readme or f"autosd {command} " in readme
