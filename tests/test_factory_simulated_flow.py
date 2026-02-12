"""End-to-end simulated local factory flow using mock provider and local services."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from automated_software_developer.agent.deploy import (
    DeploymentOrchestrator,
    default_deployment_targets,
)
from automated_software_developer.agent.incidents.engine import IncidentEngine
from automated_software_developer.agent.patching import PatchEngine
from automated_software_developer.agent.portfolio.registry import PortfolioRegistry
from automated_software_developer.agent.preauth.grants import create_grant, save_grant
from automated_software_developer.agent.preauth.keys import init_keys, load_private_key
from automated_software_developer.agent.telemetry.events import TelemetryEvent, append_event
from automated_software_developer.agent.telemetry.policy import TelemetryPolicy
from automated_software_developer.agent.telemetry.store import TelemetryStore
from automated_software_developer.cli import app


def _mock_responses() -> list[dict[str, object]]:
    verify = (
        'python -c "from pathlib import Path; '
        "assert Path('artifact.txt').read_text(encoding='utf-8').strip() == 'ok'\""
    )
    return [
        {
            "project_name": "Factory Project",
            "product_brief": "Build and verify a local artifact.",
            "personas": ["Operator"],
            "stories": [
                {
                    "id": "story-1",
                    "title": "Create artifact",
                    "story": "As an operator, I want artifact output so that validation passes.",
                    "acceptance_criteria": [
                        "Given run completion, when checks execute, then artifact.txt contains ok"
                    ],
                    "nfr_tags": ["reliability"],
                    "dependencies": [],
                    "verification_commands": [verify],
                }
            ],
            "nfrs": {
                "security": ["No secrets in artifacts"],
                "privacy": [],
                "performance": [],
                "reliability": ["Checks pass"],
                "observability": [],
                "ux_accessibility": [],
                "compliance": [],
            },
            "ambiguities": [],
            "contradictions": [],
            "missing_constraints": [],
            "edge_cases": [],
            "external_dependencies": [],
            "assumptions": [
                {
                    "assumption": "artifact value is ok",
                    "testable_criterion": (
                        "Given checks run, when artifact is read, then value equals ok"
                    ),
                }
            ],
            "stack_rationale": "Python local flow",
            "global_verification_commands": [verify],
        },
        {
            "overview": "Simple architecture",
            "components": [
                {
                    "id": "core",
                    "name": "Core",
                    "responsibilities": ["Write artifact"],
                    "interfaces": ["cli"],
                    "dependencies": [],
                }
            ],
            "adrs": [
                {
                    "id": "ADR-001",
                    "title": "Use text file",
                    "status": "accepted",
                    "context": "Need simple output",
                    "decision": "Write artifact.txt",
                    "consequences": ["Simple IO"],
                }
            ],
        },
        {
            "summary": "create artifact and readme",
            "operations": [
                {"op": "write_file", "path": "artifact.txt", "content": "ok\n"},
                {"op": "write_file", "path": "README.md", "content": "# Factory Project\n"},
            ],
            "verification_commands": [],
        },
    ]


def test_full_simulated_factory_flow(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    output_dir = tmp_path / "generated"
    responses_path = tmp_path / "mock_responses.json"
    responses_path.write_text(json.dumps(_mock_responses(), indent=2), encoding="utf-8")

    run_result = runner.invoke(
        app,
        [
            "run",
            "--provider",
            "mock",
            "--mock-responses-file",
            str(responses_path),
            "--requirements-text",
            "Create artifact project",
            "--output-dir",
            str(output_dir),
            "--security-scan-mode",
            "off",
        ],
    )
    assert run_result.exit_code == 0

    registry_path = tmp_path / "registry.jsonl"
    registry = PortfolioRegistry(write_path=registry_path, read_paths=[registry_path])
    registry.register_project(
        project_id="factory-proj",
        name="Factory Project",
        domain="ops",
        platforms=["cli_tool"],
        metadata={"local_path": str(output_dir)},
    )

    patch_engine = PatchEngine(registry=registry)
    patch_outcome = patch_engine.patch_project(
        "factory-proj",
        reason="maintenance",
        auto_push=False,
        create_tag=False,
    )
    assert patch_outcome.success is True

    deploy = DeploymentOrchestrator(registry=registry, targets=default_deployment_targets())
    incidents_path = tmp_path / "incidents.jsonl"
    incident_engine = IncidentEngine(
        registry=registry,
        patch_engine=patch_engine,
        deployment_orchestrator=deploy,
        incidents_path=incidents_path,
    )
    incident = incident_engine.create_incident(
        project_id="factory-proj",
        source="health_check",
        severity="medium",
        signal_summary="simulated failure",
        proposed_fix="apply bounded patch",
    )
    heal = incident_engine.heal_project(
        project_ref="factory-proj",
        incident_id=incident.incident_id,
        auto_push=False,
        deploy_target="generic_container",
        environment="staging",
        execute_deploy=False,
    )
    assert heal.incident.status == "resolved"
    assert heal.incident.postmortem_path is not None
    assert Path(heal.incident.postmortem_path).exists()

    policy = TelemetryPolicy.from_mode("anonymous", retention_days=30)
    events_path = output_dir / ".autosd" / "telemetry" / "events.jsonl"
    append_event(
        events_path,
        TelemetryEvent.from_dict(
            {
                "event_type": "error_count",
                "timestamp": datetime.now(tz=UTC).isoformat(),
                "metric_name": "errors",
                "value": 1,
                "project_id": "factory-proj",
            },
            policy,
        ),
    )
    store = TelemetryStore(db_path=tmp_path / "telemetry.db")
    store.ingest_events_file(project_id="factory-proj", events_path=events_path, policy=policy)
    report = store.report_project("factory-proj")
    assert report.event_count >= 1

    monkeypatch.setenv("AUTOSD_PREAUTH_HOME", str(tmp_path / "preauth"))
    init_keys()
    private_key = load_private_key()
    grant = create_grant(
        issuer="owner",
        scope={"project_ids": ["factory-proj"], "domains": [], "platforms": []},
        capabilities={
            "auto_push": False,
            "auto_merge_pr": False,
            "auto_deploy_dev": True,
            "auto_deploy_staging": True,
            "auto_deploy_prod": True,
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

    blocked = runner.invoke(
        app,
        [
            "deploy",
            "--project",
            "factory-proj",
            "--env",
            "prod",
            "--target",
            "generic_container",
            "--registry-path",
            str(registry_path),
        ],
    )
    assert blocked.exit_code != 0

    allowed = runner.invoke(
        app,
        [
            "deploy",
            "--project",
            "factory-proj",
            "--env",
            "prod",
            "--target",
            "generic_container",
            "--registry-path",
            str(registry_path),
            "--preauth-grant",
            grant.grant_id,
            "--force",
        ],
    )
    assert allowed.exit_code == 0
