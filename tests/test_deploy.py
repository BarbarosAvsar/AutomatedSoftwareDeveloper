"""Tests for deployment target orchestrator and CLI wiring."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from automated_software_developer.agent.deploy import (
    DeploymentOrchestrator,
    default_deployment_targets,
)
from automated_software_developer.agent.gitops import GitOpsManager
from automated_software_developer.agent.portfolio.registry import PortfolioRegistry
from automated_software_developer.cli import app


def _init_repo(path: Path) -> None:
    manager = GitOpsManager()
    path.mkdir(parents=True, exist_ok=True)
    manager.ensure_repository(path)
    (path / "README.md").write_text("# Deploy Repo\n", encoding="utf-8")
    manager.commit_push_tag(
        repo_dir=path,
        message="chore: init",
        branch=manager.current_branch(path),
        auto_push=False,
        tag=None,
    )


def test_deployment_orchestrator_scaffold_flow(tmp_path: Path) -> None:
    repo = tmp_path / "deploy-project"
    _init_repo(repo)
    registry_path = tmp_path / "registry.jsonl"
    registry = PortfolioRegistry(write_path=registry_path, read_paths=[registry_path])
    registry.register_project(
        project_id="deploy-1",
        name="Deploy One",
        domain="web",
        platforms=["web_app"],
        metadata={"local_path": str(repo)},
    )

    orchestrator = DeploymentOrchestrator(
        registry=registry,
        targets=default_deployment_targets(),
    )
    deploy_result = orchestrator.deploy(
        project_ref="deploy-1",
        environment="staging",
        target="generic_container",
        strategy="canary",
        execute=False,
    )
    assert deploy_result.success is True
    assert deploy_result.scaffold_only is True

    updated = registry.get("deploy-1")
    assert updated is not None
    assert updated.last_deploy is not None
    assert updated.last_deploy.environment == "staging"

    rollback_result = orchestrator.rollback(
        project_ref="deploy-1",
        environment="staging",
        target="generic_container",
        execute=False,
    )
    assert rollback_result.success is True

    promote_result = orchestrator.promote(
        project_ref="deploy-1",
        source_environment="staging",
        target_environment="prod",
        target="generic_container",
        execute=False,
    )
    assert promote_result.success is True


def test_deploy_cli_smoke(tmp_path: Path) -> None:
    repo = tmp_path / "deploy-cli"
    _init_repo(repo)
    registry_path = tmp_path / "registry.jsonl"
    registry = PortfolioRegistry(write_path=registry_path, read_paths=[registry_path])
    registry.register_project(
        project_id="deploy-cli",
        name="Deploy CLI",
        domain="web",
        platforms=["web_app"],
        metadata={"local_path": str(repo)},
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "deploy",
            "--project",
            "deploy-cli",
            "--env",
            "dev",
            "--target",
            "github_pages",
            "--registry-path",
            str(registry_path),
        ],
    )
    assert result.exit_code == 0
    assert "Deploy Result" in result.stdout
