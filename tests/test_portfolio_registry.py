"""Tests for portfolio registry, schema validation, dashboard API, and CLI commands."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from automated_software_developer.agent.portfolio.dashboard import resolve_dashboard_request
from automated_software_developer.agent.portfolio.registry import PortfolioRegistry
from automated_software_developer.agent.portfolio.schemas import RegistryEntry
from automated_software_developer.cli import app


def test_registry_crud_and_retire(tmp_path) -> None:
    registry_path = tmp_path / "registry.jsonl"
    registry = PortfolioRegistry(write_path=registry_path, read_paths=[registry_path])
    created = registry.register_project(
        project_id="proj-1",
        name="Project One",
        domain="saas",
        platforms=["web_app"],
        repo_url="https://example.test/repo.git",
    )
    assert created.project_id == "proj-1"
    fetched = registry.get("proj-1")
    assert fetched is not None
    assert fetched.name == "Project One"

    updated = registry.update("proj-1", health_status="healthy", ci_status="green")
    assert updated.health_status == "healthy"
    assert updated.ci_status == "green"

    active_entries = registry.list_entries(include_archived=False)
    assert len(active_entries) == 1

    retired = registry.retire("proj-1", reason="sunset")
    assert retired.archived is True
    assert retired.automation_halted is True

    assert registry.list_entries(include_archived=False) == []
    archived_entries = registry.list_entries(include_archived=True)
    assert len(archived_entries) == 1
    assert archived_entries[0].metadata["retired_reason"] == "sunset"


def test_registry_schema_rejects_invalid_payload() -> None:
    with pytest.raises(ValueError):
        RegistryEntry.from_dict({"project_id": "missing-fields"})


def test_dashboard_resolver_returns_redacted_project_payload(tmp_path) -> None:
    registry_path = tmp_path / "registry.jsonl"
    registry = PortfolioRegistry(write_path=registry_path, read_paths=[registry_path])
    registry.register_project(
        project_id="proj-2",
        name="Project Two",
        domain="internal",
        platforms=["cli_tool"],
        repo_url="https://user:super-secret-token@example.test/repo.git",
    )

    status_code, health_payload = resolve_dashboard_request(registry, "/health")
    assert status_code == 200
    assert health_payload["status"] == "ok"

    status_code, projects_payload = resolve_dashboard_request(registry, "/projects")
    assert status_code == 200
    assert projects_payload["count"] == 1
    repo_url = projects_payload["projects"][0]["repo_url"]
    assert "super-secret-token" not in repo_url

    status_code, project_payload = resolve_dashboard_request(registry, "/projects/proj-2")
    assert status_code == 200
    assert project_payload["project"]["project_id"] == "proj-2"

    status_code, missing_payload = resolve_dashboard_request(registry, "/projects/missing")
    assert status_code == 404
    assert "not found" in missing_payload["error"]


def test_projects_cli_smoke(tmp_path) -> None:
    registry_path = tmp_path / "registry.jsonl"
    registry = PortfolioRegistry(write_path=registry_path, read_paths=[registry_path])
    registry.register_project(
        project_id="proj-cli",
        name="CLI Project",
        domain="tools",
        platforms=["cli_tool"],
    )

    runner = CliRunner()
    list_result = runner.invoke(
        app,
        ["projects", "list", "--registry-path", str(registry_path)],
    )
    assert list_result.exit_code == 0
    assert "proj-cli" in list_result.stdout

    show_result = runner.invoke(
        app,
        ["projects", "show", "proj-cli", "--registry-path", str(registry_path)],
    )
    assert show_result.exit_code == 0
    assert "CLI Project" in show_result.stdout

    retire_result = runner.invoke(
        app,
        [
            "projects",
            "retire",
            "proj-cli",
            "--reason",
            "done",
            "--registry-path",
            str(registry_path),
        ],
    )
    assert retire_result.exit_code == 0
    assert "retired" in retire_result.stdout.lower()
