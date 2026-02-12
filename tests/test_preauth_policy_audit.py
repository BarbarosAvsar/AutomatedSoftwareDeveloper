"""Tests for preauthorization grants, policy resolution, and audit logging."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from automated_software_developer.agent.audit import AuditLogger
from automated_software_developer.agent.policy.engine import (
    evaluate_action,
    resolve_effective_policy,
)
from automated_software_developer.agent.preauth.grants import (
    create_grant,
    revoke_grant,
    save_grant,
)
from automated_software_developer.agent.preauth.keys import init_keys, load_private_key
from automated_software_developer.agent.preauth.verify import verify_grant


def _grant_kwargs() -> dict[str, object]:
    return {
        "scope": {"project_ids": ["proj-1"], "domains": [], "platforms": []},
        "capabilities": {
            "auto_push": True,
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
        "required_gates": {
            "quality_gates": True,
            "security_scan_mode": "if-available",
            "sbom": "if-available",
            "dependency_audit": "if-available",
            "canary_required_for_prod": True,
            "min_test_scope": "suite",
        },
        "budgets": {
            "max_deploys_per_day": 5,
            "max_patches_per_incident": 2,
            "max_auto_merges_per_day": 2,
            "max_failures_before_halt": 3,
        },
        "telemetry": {
            "allowed_modes": ["off", "anonymous"],
            "retention_max_days": 30,
            "event_allowlist_ref": "default",
        },
    }


def test_preauth_signature_verify_and_revocation(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "preauth"
    monkeypatch.setenv("AUTOSD_PREAUTH_HOME", str(home))
    init_keys()
    private_key = load_private_key()
    grant = create_grant(
        issuer="owner",
        expires_in_hours=1,
        break_glass=False,
        private_key=private_key,
        **_grant_kwargs(),
    )
    save_grant(grant)

    verification = verify_grant(
        grant_id=grant.grant_id,
        required_capability="auto_deploy_prod",
        project_id="proj-1",
        environment="prod",
    )
    assert verification.valid is True

    revoke_grant(grant.grant_id, reason="test revoke")
    revoked = verify_grant(
        grant_id=grant.grant_id,
        required_capability="auto_deploy_prod",
        project_id="proj-1",
        environment="prod",
    )
    assert revoked.valid is False
    assert revoked.reason == "grant_revoked"


def test_preauth_expiry_and_policy_resolution(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "preauth"
    monkeypatch.setenv("AUTOSD_PREAUTH_HOME", str(home))
    init_keys()
    private_key = load_private_key()
    grant = create_grant(
        issuer="owner",
        expires_in_hours=1,
        break_glass=False,
        private_key=private_key,
        **_grant_kwargs(),
    )
    save_grant(grant)

    expired = verify_grant(
        grant_id=grant.grant_id,
        required_capability="auto_deploy_prod",
        project_id="proj-1",
        environment="prod",
        current_time=datetime.now(tz=UTC) + timedelta(hours=2),
    )
    assert expired.valid is False
    assert expired.reason == "grant_expired"

    base_only = resolve_effective_policy(project_policy=None, grant=None)
    blocked = evaluate_action(policy=base_only, action="deploy", environment="prod")
    assert blocked.allowed is False

    with_grant = resolve_effective_policy(project_policy=None, grant=grant)
    allowed = evaluate_action(policy=with_grant, action="deploy", environment="prod")
    assert allowed.allowed is True


def test_audit_log_writes_jsonl(tmp_path: Path, monkeypatch) -> None:
    audit_path = tmp_path / "audit.log.jsonl"
    monkeypatch.setenv("AUTOSD_AUDIT_LOG", str(audit_path))
    logger = AuditLogger()
    logger.log(
        project_id="proj-1",
        action="deploy",
        result="success",
        grant_id="grant-1",
        gates_run=["quality", "security"],
        commit_ref="abc123",
        tag_ref="v1.0.0",
        break_glass_used=False,
        details={"note": "done"},
    )
    line = audit_path.read_text(encoding="utf-8").strip()
    payload = json.loads(line)
    assert payload["project_id"] == "proj-1"
    assert payload["action"] == "deploy"
    assert payload["result"] == "success"
