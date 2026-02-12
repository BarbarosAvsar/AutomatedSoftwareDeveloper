"""Tests for privacy-safe telemetry validation, storage, and CLI commands."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from automated_software_developer.agent.gitops import GitOpsManager
from automated_software_developer.agent.portfolio.registry import PortfolioRegistry
from automated_software_developer.agent.telemetry.events import TelemetryEvent, append_event
from automated_software_developer.agent.telemetry.policy import TelemetryPolicy
from automated_software_developer.agent.telemetry.store import TelemetryStore
from automated_software_developer.cli import app


def _init_repo(path: Path) -> None:
    manager = GitOpsManager()
    path.mkdir(parents=True, exist_ok=True)
    manager.ensure_repository(path)
    (path / "README.md").write_text("# Telemetry Repo\n", encoding="utf-8")
    manager.commit_push_tag(
        repo_dir=path,
        message="chore: init",
        branch=manager.current_branch(path),
        auto_push=False,
        tag=None,
    )


def test_telemetry_event_validation_and_retention(tmp_path: Path) -> None:
    policy = TelemetryPolicy.from_mode("anonymous", retention_days=30)
    events_path = tmp_path / "events.jsonl"
    valid = TelemetryEvent.from_dict(
        {
            "event_type": "error_count",
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "metric_name": "errors",
            "value": 1,
            "project_id": "proj-telemetry",
            "platform": "web",
            "metadata": {"environment": "dev"},
        },
        policy,
    )
    append_event(events_path, valid)
    with events_path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "event_type": "error_count",
                    "timestamp": datetime.now(tz=UTC).isoformat(),
                    "metric_name": "errors",
                    "value": 2,
                    "project_id": "user@example.com",
                }
            )
            + "\n"
        )

    store = TelemetryStore(db_path=tmp_path / "telemetry.db")
    ingested = store.ingest_events_file(
        project_id="proj-telemetry",
        events_path=events_path,
        policy=policy,
    )
    assert ingested == 1
    report = store.report_project("proj-telemetry")
    assert report.event_count == 1

    old_event = TelemetryEvent.from_dict(
        {
            "event_type": "error_count",
            "timestamp": "2000-01-01T00:00:00+00:00",
            "metric_name": "errors",
            "value": 3,
            "project_id": "proj-telemetry",
        },
        policy,
    )
    append_event(events_path, old_event)
    store.ingest_events_file(project_id="proj-telemetry", events_path=events_path, policy=policy)
    deleted = store.enforce_retention(30)
    assert deleted >= 1


def test_telemetry_cli_enable_and_report(tmp_path: Path) -> None:
    repo = tmp_path / "project"
    _init_repo(repo)
    registry_path = tmp_path / "registry.jsonl"
    registry = PortfolioRegistry(write_path=registry_path, read_paths=[registry_path])
    registry.register_project(
        project_id="telemetry-cli",
        name="Telemetry CLI",
        domain="web",
        platforms=["web_app"],
        metadata={"local_path": str(repo)},
    )

    policy = TelemetryPolicy.from_mode("anonymous", retention_days=30)
    events_path = repo / ".autosd" / "telemetry" / "events.jsonl"
    append_event(
        events_path,
        TelemetryEvent.from_dict(
            {
                "event_type": "error_count",
                "timestamp": datetime.now(tz=UTC).isoformat(),
                "metric_name": "errors",
                "value": 1,
                "project_id": "telemetry-cli",
            },
            policy,
        ),
    )

    runner = CliRunner()
    env = {"AUTOSD_TELEMETRY_DB": str(tmp_path / "telemetry.db")}
    enable_result = runner.invoke(
        app,
        [
            "telemetry",
            "enable",
            "--project",
            "telemetry-cli",
            "--mode",
            "anonymous",
            "--registry-path",
            str(registry_path),
        ],
        env=env,
    )
    assert enable_result.exit_code == 0
    assert "Telemetry policy" in enable_result.stdout

    report_result = runner.invoke(
        app,
        [
            "telemetry",
            "report",
            "--project",
            "telemetry-cli",
            "--registry-path",
            str(registry_path),
        ],
        env=env,
    )
    assert report_result.exit_code == 0
    assert "Telemetry Report" in report_result.stdout


def test_telemetry_cli_disable_blocks_reporting(tmp_path: Path) -> None:
    repo = tmp_path / "project-disabled"
    _init_repo(repo)
    registry_path = tmp_path / "registry.jsonl"
    registry = PortfolioRegistry(write_path=registry_path, read_paths=[registry_path])
    registry.register_project(
        project_id="telemetry-off",
        name="Telemetry Off",
        domain="web",
        platforms=["web_app"],
        metadata={"local_path": str(repo)},
    )

    runner = CliRunner()
    env = {"AUTOSD_TELEMETRY_DB": str(tmp_path / "telemetry.db")}
    enable_result = runner.invoke(
        app,
        [
            "telemetry",
            "enable",
            "--project",
            "telemetry-off",
            "--mode",
            "off",
            "--registry-path",
            str(registry_path),
        ],
        env=env,
    )
    assert enable_result.exit_code == 0

    report_result = runner.invoke(
        app,
        [
            "telemetry",
            "report",
            "--project",
            "telemetry-off",
            "--registry-path",
            str(registry_path),
        ],
        env=env,
    )
    assert report_result.exit_code == 0
    assert "Telemetry is disabled" in report_result.stdout
