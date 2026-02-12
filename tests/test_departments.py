"""Tests for department-level agents and routing."""

from __future__ import annotations

import json
from pathlib import Path

from automated_software_developer.agent.audit import AuditLogger
from automated_software_developer.agent.departments.base import AgentContext, WorkOrder
from automated_software_developer.agent.departments.data_intelligence import (
    CorpusEntry,
    DataIntelligenceAgent,
)
from automated_software_developer.agent.departments.engineering import EngineeringAgent
from automated_software_developer.agent.departments.operations import ReleaseManager
from automated_software_developer.agent.departments.policy import DepartmentPolicy
from automated_software_developer.agent.departments.program_management import (
    ProgramManagementAgent,
    WorkRequest,
)
from automated_software_developer.agent.departments.security import SecurityAgent
from automated_software_developer.agent.departments.support_ops import SupportOpsAgent
from automated_software_developer.agent.policy.engine import resolve_effective_policy
from automated_software_developer.agent.preauth.grants import create_grant
from automated_software_developer.agent.preauth.keys import init_keys, load_private_key
from automated_software_developer.agent.providers.mock_provider import MockProvider


def _base_context(tmp_path: Path, policy=None, grant=None) -> AgentContext:
    resolved_policy = policy or resolve_effective_policy(project_policy=None, grant=grant)
    return AgentContext(
        project_id="proj-1",
        project_dir=tmp_path,
        policy=resolved_policy,
        grant=grant,
        audit_logger=AuditLogger(path=tmp_path / "audit.jsonl"),
        metadata={},
    )


def test_pmo_routes_and_blocks_policy(tmp_path: Path) -> None:
    policy = resolve_effective_policy(
        project_policy={"deployment": {"allow_prod": False}},
        grant=None,
    )
    context = _base_context(tmp_path, policy=policy)
    pmo = ProgramManagementAgent()
    requests = [WorkRequest(action="deploy", payload={"environment": "prod"})]
    result = pmo.plan_work(context, requests)
    assert result.halted is True
    assert "prod_deploy_blocked" in result.escalations

    allow_policy = resolve_effective_policy(
        project_policy={"deployment": {"allow_prod": True}},
        grant=None,
    )
    context = _base_context(tmp_path, policy=allow_policy)
    result = pmo.plan_work(
        context,
        [WorkRequest(action="deploy", payload={"environment": "staging"})],
    )
    assert result.halted is False
    orders = result.metadata["orders"]
    assert orders[0].department == "operations"


def test_security_agent_preauth_gate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AUTOSD_PREAUTH_HOME", str(tmp_path / "preauth"))
    init_keys()
    private_key = load_private_key()
    grant = create_grant(
        issuer="owner",
        scope={"project_ids": ["proj-1"], "domains": [], "platforms": []},
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
        budgets={"deploy": 1, "patch": 1, "merge": 0, "publish": 0},
        telemetry={"mode": "off"},
        expires_in_hours=1,
        break_glass=False,
        private_key=private_key,
    )

    policy = resolve_effective_policy(
        project_policy={"deployment": {"allow_prod": True}},
        grant=None,
    )
    context = _base_context(tmp_path, policy=policy)
    security_agent = SecurityAgent()
    decision = security_agent.handle(
        context,
        WorkOrder(department="security", action="gate_deploy", payload={"environment": "prod"}),
    )
    assert decision.halted is True

    context_with_grant = _base_context(tmp_path, policy=policy, grant=grant)
    decision = security_agent.handle(
        context_with_grant,
        WorkOrder(department="security", action="gate_deploy", payload={"environment": "prod"}),
    )
    assert decision.halted is False


def test_ops_release_creates_bundle_and_tag(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "README.md").write_text("# Demo\n", encoding="utf-8")
    release_manager = ReleaseManager()
    bundle = release_manager.create_release(
        project_dir=project_dir,
        project_id="demo",
        version="0.1.0",
        tag="v0.1.0",
    )
    assert bundle.release_dir.exists()
    payload = json.loads(bundle.manifest_path.read_text(encoding="utf-8"))
    assert payload["tag"] == "v0.1.0"


def test_engineering_agent_creates_architecture_and_gates(tmp_path: Path) -> None:
    verify = (
        "python -c \"from pathlib import Path; assert 'ok' in Path('artifact.txt').read_text()\""
    )
    responses = [
        {
            "project_name": "Dept Project",
            "product_brief": "Build artifact",
            "personas": ["Operator"],
            "stories": [
                {
                    "id": "story-1",
                    "title": "Create artifact",
                    "story": "As a user I want an artifact so that checks pass",
                    "acceptance_criteria": ["artifact.txt contains ok"],
                    "nfr_tags": ["reliability"],
                    "dependencies": [],
                    "verification_commands": [verify],
                }
            ],
            "nfrs": {
                "security": ["No secrets"],
                "privacy": [],
                "performance": [],
                "reliability": [],
                "observability": [],
                "ux_accessibility": [],
                "compliance": [],
            },
            "ambiguities": [],
            "contradictions": [],
            "missing_constraints": [],
            "edge_cases": [],
            "external_dependencies": [],
            "assumptions": [],
            "stack_rationale": "Python",
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
            "summary": "Create artifact",
            "operations": [
                {"op": "write_file", "path": "artifact.txt", "content": "ok\n"},
                {"op": "write_file", "path": "README.md", "content": "# Dept Project\n"},
            ],
            "verification_commands": [],
        },
    ]
    provider = MockProvider(responses)
    agent = EngineeringAgent(provider=provider)
    context = _base_context(
        tmp_path,
        policy=resolve_effective_policy(project_policy=None, grant=None),
    )
    context = AgentContext(
        project_id=context.project_id,
        project_dir=context.project_dir,
        policy=context.policy,
        grant=context.grant,
        audit_logger=context.audit_logger,
        metadata={"requirements": "Build artifact", "output_dir": tmp_path},
    )
    result = agent.handle(context)
    artifacts = [path for path in result.artifacts if path is not None]
    assert any("architecture.md" in str(path) for path in artifacts)


def test_data_agent_ingest_license_checked(tmp_path: Path) -> None:
    policy = DepartmentPolicy().with_allowed_licenses(["MIT"])
    agent = DataIntelligenceAgent(policy=policy)
    entries = [
        CorpusEntry(source="repo1", license="MIT", summary="ok", content_hash="abcd1234"),
    ]
    context = _base_context(tmp_path)
    result = agent.handle(
        context,
        WorkOrder(
            department="data_intelligence",
            action="ingest_corpus",
            payload={"entries": entries, "analytics_dir": tmp_path / "analytics"},
        ),
    )
    assert result.halted is False
    assert result.artifacts[0].exists()

    blocked_entries = [
        CorpusEntry(source="repo2", license="GPL-3.0", summary="bad", content_hash="ffff0000"),
    ]
    blocked = agent.handle(
        context,
        WorkOrder(
            department="data_intelligence",
            action="ingest_corpus",
            payload={"entries": blocked_entries, "analytics_dir": tmp_path / "analytics"},
        ),
    )
    assert blocked.halted is True


def test_support_triage_creates_ticket(tmp_path: Path) -> None:
    agent = SupportOpsAgent()
    context = _base_context(tmp_path)
    result = agent.handle(
        context,
        WorkOrder(
            department="support_ops",
            action="triage",
            payload={"summary": "outage", "severity": "high", "category": "outage"},
        ),
    )
    assert result.artifacts[0].exists()
