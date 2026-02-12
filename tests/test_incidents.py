"""Tests for incidents ledger and autonomous healing workflow."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from automated_software_developer.agent.deploy import (
    DeploymentOrchestrator,
    default_deployment_targets,
)
from automated_software_developer.agent.gitops import GitOpsManager
from automated_software_developer.agent.incidents.engine import IncidentEngine
from automated_software_developer.agent.incidents.model import load_incidents
from automated_software_developer.agent.patching import PatchEngine
from automated_software_developer.agent.portfolio.registry import PortfolioRegistry
from automated_software_developer.cli import app


def _init_repo(path: Path) -> None:
    manager = GitOpsManager()
    path.mkdir(parents=True, exist_ok=True)
    manager.ensure_repository(path)
    (path / "README.md").write_text("# Incident Repo\n", encoding="utf-8")
    manager.commit_push_tag(
        repo_dir=path,
        message="chore: init",
        branch=manager.current_branch(path),
        auto_push=False,
        tag=None,
    )


def test_incident_healing_flow_creates_postmortem(tmp_path: Path) -> None:
    repo = tmp_path / "incident-project"
    _init_repo(repo)
    registry_path = tmp_path / "registry.jsonl"
    incidents_path = tmp_path / "incidents.jsonl"
    registry = PortfolioRegistry(write_path=registry_path, read_paths=[registry_path])
    registry.register_project(
        project_id="inc-1",
        name="Incident One",
        domain="ops",
        platforms=["api_service"],
        metadata={"local_path": str(repo)},
    )

    patch_engine = PatchEngine(registry=registry)
    deploy_orchestrator = DeploymentOrchestrator(
        registry=registry,
        targets=default_deployment_targets(),
    )
    engine = IncidentEngine(
        registry=registry,
        patch_engine=patch_engine,
        deployment_orchestrator=deploy_orchestrator,
        incidents_path=incidents_path,
    )
    incident = engine.create_incident(
        project_id="inc-1",
        source="health_check",
        severity="high",
        signal_summary="health endpoint failed repeatedly",
        proposed_fix="add regression test and patch endpoint behavior",
    )
    result = engine.heal_project(
        project_ref="inc-1",
        incident_id=incident.incident_id,
        auto_push=False,
        deploy_target="generic_container",
        environment="staging",
        execute_deploy=False,
    )

    assert result.incident.status == "resolved"
    assert result.patch_outcome.success is True
    assert result.incident.postmortem_path is not None
    assert Path(result.incident.postmortem_path).exists()


def test_incident_detection_and_heal_records_postmortem(tmp_path: Path) -> None:
    repo = tmp_path / "signal-project"
    _init_repo(repo)
    registry_path = tmp_path / "registry.jsonl"
    incidents_path = tmp_path / "incidents.jsonl"
    registry = PortfolioRegistry(write_path=registry_path, read_paths=[registry_path])
    registry.register_project(
        project_id="signal-1",
        name="Signal One",
        domain="ops",
        platforms=["api_service"],
        metadata={"local_path": str(repo)},
    )

    engine = IncidentEngine(
        registry=registry,
        patch_engine=PatchEngine(registry=registry),
        deployment_orchestrator=DeploymentOrchestrator(
            registry=registry,
            targets=default_deployment_targets(),
        ),
        incidents_path=incidents_path,
    )
    incident = engine.detect_from_signals(project_id="signal-1", error_count=6, crash_count=0)
    assert incident is not None

    result = engine.heal_project(
        project_ref="signal-1",
        incident_id=incident.incident_id,
        auto_push=False,
        deploy_target=None,
        environment="staging",
        execute_deploy=False,
    )

    records = load_incidents(incidents_path)
    assert any(record.incident_id == incident.incident_id for record in records)
    assert result.incident.postmortem_path is not None
    assert Path(result.incident.postmortem_path).exists()


def test_incidents_cli_list_show_and_heal(tmp_path: Path) -> None:
    repo = tmp_path / "incident-cli"
    _init_repo(repo)
    registry_path = tmp_path / "registry.jsonl"
    incidents_path = tmp_path / "incidents.jsonl"
    registry = PortfolioRegistry(write_path=registry_path, read_paths=[registry_path])
    registry.register_project(
        project_id="inc-cli",
        name="Incident CLI",
        domain="ops",
        platforms=["api_service"],
        metadata={"local_path": str(repo)},
    )

    runner = CliRunner()
    heal_result = runner.invoke(
        app,
        [
            "heal",
            "--project",
            "inc-cli",
            "--target",
            "generic_container",
            "--registry-path",
            str(registry_path),
            "--incidents-path",
            str(incidents_path),
        ],
    )
    assert heal_result.exit_code == 0
    assert "Heal Result" in heal_result.stdout

    list_result = runner.invoke(
        app,
        [
            "incidents",
            "list",
            "--registry-path",
            str(registry_path),
            "--incidents-path",
            str(incidents_path),
        ],
    )
    assert list_result.exit_code == 0
    assert "Incidents" in list_result.stdout
