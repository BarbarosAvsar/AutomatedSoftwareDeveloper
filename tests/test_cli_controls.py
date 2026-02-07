"""CLI tests for halt/resume controls and preauth management commands."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from automated_software_developer.agent.portfolio.registry import PortfolioRegistry
from automated_software_developer.agent.preauth.grants import create_grant, revoke_grant, save_grant
from automated_software_developer.agent.preauth.keys import init_keys, load_private_key
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


def test_preauth_active_only_list_filters_revoked(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AUTOSD_PREAUTH_HOME", str(tmp_path / "preauth"))
    init_keys()
    private_key = load_private_key()
    grant = create_grant(
        issuer="owner",
        scope={"project_ids": "*", "domains": [], "platforms": []},
        capabilities={
            "auto_push": False,
            "auto_merge_pr": False,
            "auto_deploy_dev": True,
            "auto_deploy_staging": True,
            "auto_deploy_prod": False,
            "auto_rollback": True,
            "auto_heal": True,
            "create_repos": False,
            "rotate_deployments": False,
            "publish_app_store": False,
        },
        required_gates={
            "quality_gates": True,
            "security_scan_mode": "if-available",
            "sbom": "if-available",
            "dependency_audit": "if-available",
            "canary_required_for_prod": True,
            "min_test_scope": "suite",
        },
        budgets={
            "max_deploys_per_day": 5,
            "max_patches_per_incident": 2,
            "max_auto_merges_per_day": 2,
            "max_failures_before_halt": 3,
        },
        telemetry={
            "allowed_modes": ["off", "anonymous"],
            "retention_max_days": 30,
            "event_allowlist_ref": "default",
        },
        expires_in_hours=1,
        break_glass=False,
        private_key=private_key,
    )
    save_grant(grant)
    revoke_grant(grant.grant_id, reason="test")

    runner = CliRunner()
    result = runner.invoke(app, ["preauth", "list", "--active-only"])
    assert result.exit_code == 0
    assert "No grants matched" in result.stdout
