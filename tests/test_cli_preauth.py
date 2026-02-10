"""CLI tests for preauthorization-gated deployment actions."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from automated_software_developer.agent.gitops import GitOpsManager
from automated_software_developer.agent.portfolio.registry import PortfolioRegistry
from automated_software_developer.agent.preauth.grants import create_grant, revoke_grant, save_grant
from automated_software_developer.agent.preauth.keys import init_keys, load_private_key
from automated_software_developer.cli import app


def _init_repo(path: Path) -> None:
    manager = GitOpsManager()
    path.mkdir(parents=True, exist_ok=True)
    manager.ensure_repository(path)
    (path / "README.md").write_text("# Preauth CLI Repo\n", encoding="utf-8")
    manager.commit_push_tag(
        repo_dir=path,
        message="chore: init",
        branch=manager.current_branch(path),
        auto_push=False,
        tag=None,
    )


def _create_prod_grant() -> str:
    private_key = load_private_key()
    grant = create_grant(
        issuer="owner",
        scope={"project_ids": ["preauth-proj"], "domains": [], "platforms": []},
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
    return grant.grant_id


def test_prod_deploy_requires_valid_preauth(tmp_path: Path, monkeypatch) -> None:
    preauth_home = tmp_path / "preauth"
    monkeypatch.setenv("AUTOSD_PREAUTH_HOME", str(preauth_home))
    init_keys()

    repo = tmp_path / "project"
    _init_repo(repo)
    registry_path = tmp_path / "registry.jsonl"
    registry = PortfolioRegistry(write_path=registry_path, read_paths=[registry_path])
    registry.register_project(
        project_id="preauth-proj",
        name="Preauth Project",
        domain="ops",
        platforms=["api_service"],
        metadata={"local_path": str(repo)},
    )

    runner = CliRunner()
    blocked = runner.invoke(
        app,
        [
            "deploy",
            "--project",
            "preauth-proj",
            "--env",
            "prod",
            "--target",
            "generic_container",
            "--registry-path",
            str(registry_path),
        ],
    )
    assert blocked.exit_code != 0

    grant_id = _create_prod_grant()
    allowed = runner.invoke(
        app,
        [
            "deploy",
            "--project",
            "preauth-proj",
            "--env",
            "prod",
            "--target",
            "generic_container",
            "--registry-path",
            str(registry_path),
            "--preauth-grant",
            grant_id,
            "--force",
        ],
    )
    assert allowed.exit_code == 0

    revoke_grant(grant_id, reason="test")
    revoked = runner.invoke(
        app,
        [
            "deploy",
            "--project",
            "preauth-proj",
            "--env",
            "prod",
            "--target",
            "generic_container",
            "--registry-path",
            str(registry_path),
            "--preauth-grant",
            grant_id,
        ],
    )
    assert revoked.exit_code != 0


def test_promote_requires_valid_preauth_and_rejects_expired(tmp_path: Path, monkeypatch) -> None:
    preauth_home = tmp_path / "preauth"
    monkeypatch.setenv("AUTOSD_PREAUTH_HOME", str(preauth_home))
    init_keys()

    repo = tmp_path / "project"
    _init_repo(repo)
    registry_path = tmp_path / "registry.jsonl"
    registry = PortfolioRegistry(write_path=registry_path, read_paths=[registry_path])
    registry.register_project(
        project_id="preauth-proj",
        name="Preauth Project",
        domain="ops",
        platforms=["api_service"],
        metadata={"local_path": str(repo)},
    )

    runner = CliRunner()
    blocked = runner.invoke(
        app,
        [
            "promote",
            "--project",
            "preauth-proj",
            "--from",
            "staging",
            "--to",
            "prod",
            "--target",
            "generic_container",
            "--registry-path",
            str(registry_path),
            "--force",
        ],
    )
    assert blocked.exit_code != 0
    assert "AUTOSD-PREAUTH-REQUIRED" in blocked.output

    private_key = load_private_key()
    expired = create_grant(
        issuer="owner",
        scope={"project_ids": ["preauth-proj"], "domains": [], "platforms": []},
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
    expired.payload["expires_at"] = "2000-01-01T00:00:00+00:00"
    save_grant(expired)

    expired_result = runner.invoke(
        app,
        [
            "promote",
            "--project",
            "preauth-proj",
            "--from",
            "staging",
            "--to",
            "prod",
            "--target",
            "generic_container",
            "--registry-path",
            str(registry_path),
            "--preauth-grant",
            expired.grant_id,
            "--force",
        ],
    )
    assert expired_result.exit_code != 0
    assert "AUTOSD-PREAUTH-INVALID" in expired_result.output


def test_rollback_rejects_revoked_grant(tmp_path: Path, monkeypatch) -> None:
    preauth_home = tmp_path / "preauth"
    monkeypatch.setenv("AUTOSD_PREAUTH_HOME", str(preauth_home))
    init_keys()

    repo = tmp_path / "project"
    _init_repo(repo)
    registry_path = tmp_path / "registry.jsonl"
    registry = PortfolioRegistry(write_path=registry_path, read_paths=[registry_path])
    registry.register_project(
        project_id="preauth-proj",
        name="Preauth Project",
        domain="ops",
        platforms=["api_service"],
        metadata={"local_path": str(repo)},
    )

    grant_id = _create_prod_grant()
    revoke_grant(grant_id, reason="revoked")

    runner = CliRunner()
    revoked = runner.invoke(
        app,
        [
            "rollback",
            "--project",
            "preauth-proj",
            "--env",
            "staging",
            "--target",
            "generic_container",
            "--registry-path",
            str(registry_path),
            "--preauth-grant",
            grant_id,
            "--force",
        ],
    )
    assert revoked.exit_code != 0
    assert "AUTOSD-PREAUTH-INVALID" in revoked.output
