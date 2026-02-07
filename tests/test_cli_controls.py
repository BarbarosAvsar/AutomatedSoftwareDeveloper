"""CLI tests for halt/resume controls and preauth management commands."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from automated_software_developer.agent.portfolio.registry import PortfolioRegistry
from automated_software_developer.cli import app


def test_halt_resume_commands(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.jsonl"
    registry = PortfolioRegistry(write_path=registry_path, read_paths=[registry_path])
    registry.register_project(
        project_id="control-proj",
        name="Control Project",
        domain="ops",
        platforms=["cli_tool"],
    )

    runner = CliRunner()
    halt = runner.invoke(
        app,
        [
            "halt",
            "--project",
            "control-proj",
            "--registry-path",
            str(registry_path),
        ],
    )
    assert halt.exit_code == 0
    assert "halted" in halt.stdout.lower()

    halted_entry = registry.get("control-proj")
    assert halted_entry is not None
    assert halted_entry.automation_halted is True

    resume = runner.invoke(
        app,
        [
            "resume",
            "--project",
            "control-proj",
            "--registry-path",
            str(registry_path),
        ],
    )
    assert resume.exit_code == 0
    resumed_entry = registry.get("control-proj")
    assert resumed_entry is not None
    assert resumed_entry.automation_halted is False


def test_preauth_cli_commands(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AUTOSD_PREAUTH_HOME", str(tmp_path / "preauth"))
    runner = CliRunner()

    init_result = runner.invoke(app, ["preauth", "init-keys"])
    assert init_result.exit_code == 0

    create_result = runner.invoke(
        app,
        [
            "preauth",
            "create-grant",
            "--project-ids",
            "demo-proj",
            "--auto-deploy-prod",
            "--expires-in-hours",
            "1",
        ],
    )
    assert create_result.exit_code == 0
    assert "Grant created" in create_result.stdout

    list_result = runner.invoke(app, ["preauth", "list"])
    assert list_result.exit_code == 0
    assert "Preauth Grants" in list_result.stdout
