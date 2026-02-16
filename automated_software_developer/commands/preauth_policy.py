"""CLI command registrations."""

from __future__ import annotations

# mypy: ignore-errors
# ruff: noqa: B008,F403,F405,I001
from automated_software_developer.commands.common import *


@policy_app.command("show")
def policy_show(
    project: Annotated[
        str | None,
        typer.Option("--project", help="Optional project ID or name for scope checks."),
    ] = None,
    preauth_grant: Annotated[
        str | None,
        typer.Option("--preauth-grant", help="Optional grant ID to introspect."),
    ] = None,
    environment: Annotated[
        str | None,
        typer.Option("--env", help="Optional environment for grant scope checks."),
    ] = None,
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
) -> None:
    """Show resolved policy and optional preauthorization grant status."""
    project_id: str | None = None
    project_dir: Path | None = None
    if project is not None:
        registry = _create_registry(registry_path)
        entry = registry.get(project)
        if entry is None:
            raise typer.BadParameter(f"Project '{project}' not found.")
        project_id = entry.project_id
        project_dir = _resolve_project_path(entry.metadata)

    grant_result = None
    grant = None
    if preauth_grant is not None:
        grant_result = verify_grant(
            grant_id=preauth_grant,
            project_id=project_id,
            environment=environment,
        )
        grant = grant_result.grant if grant_result.valid else None

    policy = resolve_effective_policy(project_policy=None, grant=grant)
    if project_dir is not None:
        _write_policy_snapshot(project_dir, policy.to_dict())

    policy_table = Table(title="Policy Snapshot")
    policy_table.add_column("Area")
    policy_table.add_column("Settings")
    telemetry = policy.payload.get("telemetry", {})
    deployment = policy.payload.get("deployment", {})
    gitops = policy.payload.get("gitops", {})
    app_store = policy.payload.get("app_store", {})
    budgets = policy.payload.get("budgets", {})
    policy_table.add_row(
        "telemetry",
        f"mode={telemetry.get('mode')} retention_days={telemetry.get('retention_days')}",
    )
    policy_table.add_row(
        "deployment",
        (
            f"dev={deployment.get('allow_dev')} "
            f"staging={deployment.get('allow_staging')} "
            f"prod={deployment.get('allow_prod')} "
            f"canary_required={deployment.get('require_canary_for_prod')}"
        ),
    )
    policy_table.add_row(
        "gitops",
        f"auto_push={gitops.get('auto_push')} auto_merge={gitops.get('auto_merge')}",
    )
    policy_table.add_row(
        "app_store",
        f"publish_enabled={app_store.get('publish_enabled')}",
    )
    policy_table.add_row(
        "budgets",
        json.dumps(budgets, indent=2),
    )
    console.print(policy_table)

    if preauth_grant is not None:
        grant_table = Table(title="Preauth Grant Status")
        grant_table.add_column("Field")
        grant_table.add_column("Value")
        if grant_result is None:
            grant_table.add_row("status", "unknown")
        elif not grant_result.valid:
            grant_table.add_row("status", "invalid")
            grant_table.add_row("reason", grant_result.reason)
            if grant_result.grant is not None:
                grant_table.add_row("grant_id", grant_result.grant.grant_id)
        else:
            grant_table.add_row("status", "valid")
            grant_table.add_row("grant_id", grant.grant_id if grant else "unknown")
            expires_at = grant.expires_at() if grant else None
            grant_table.add_row(
                "expires_at",
                expires_at.isoformat() if expires_at else "unknown",
            )
            grant_table.add_row(
                "break_glass",
                "true" if grant_break_glass(grant) else "false",
            )
            if grant is not None:
                capabilities = grant.payload.get("capabilities", {})
                enabled = sorted(
                    key for key, value in capabilities.items() if isinstance(value, bool) and value
                )
                grant_table.add_row("capabilities", ", ".join(enabled) or "none")
        console.print(grant_table)
        if grant_result is not None and not grant_result.valid:
            raise typer.Exit(code=1)


@preauth_app.command("init-keys")
def preauth_init_keys() -> None:
    """Initialize local Ed25519 keypair for preauthorization grants."""
    paths = init_keys()
    console.print(f"Private key: {paths.private_key_path}")
    console.print(f"Public key: {paths.public_key_path}")


@preauth_app.command("rotate-keys")
def preauth_rotate_keys() -> None:
    """Rotate preauthorization keypair while retaining archived public keys."""
    paths = rotate_keys()
    console.print(f"Rotated private key: {paths.private_key_path}")
    console.print(f"Rotated public key: {paths.public_key_path}")


@preauth_app.command("create-grant")
def preauth_create_grant(
    issuer: Annotated[str, typer.Option(help="Issuer label for audit trail.")] = "owner",
    project_ids: Annotated[
        list[str] | None,
        typer.Option("--project-ids", help="Allowed project IDs; repeat flag for multiple."),
    ] = None,
    expires_in_hours: Annotated[
        int,
        typer.Option(help="Grant expiry in hours."),
    ] = 1,
    auto_push: Annotated[
        bool,
        typer.Option("--auto-push/--no-auto-push"),
    ] = False,
    auto_merge_pr: Annotated[
        bool,
        typer.Option("--auto-merge-pr/--no-auto-merge-pr"),
    ] = False,
    auto_deploy_dev: Annotated[
        bool,
        typer.Option("--auto-deploy-dev/--no-auto-deploy-dev"),
    ] = True,
    auto_deploy_staging: Annotated[
        bool,
        typer.Option("--auto-deploy-staging/--no-auto-deploy-staging"),
    ] = True,
    auto_deploy_prod: Annotated[
        bool,
        typer.Option("--auto-deploy-prod/--no-auto-deploy-prod"),
    ] = False,
    auto_rollback: Annotated[
        bool,
        typer.Option("--auto-rollback/--no-auto-rollback"),
    ] = True,
    auto_heal: Annotated[
        bool,
        typer.Option("--auto-heal/--no-auto-heal"),
    ] = True,
    create_repos: Annotated[
        bool,
        typer.Option("--create-repos/--no-create-repos"),
    ] = False,
    rotate_deployments: Annotated[
        bool,
        typer.Option("--rotate-deployments/--no-rotate-deployments"),
    ] = False,
    publish_app_store: Annotated[
        bool,
        typer.Option("--publish-app-store/--no-publish-app-store"),
    ] = False,
    break_glass: Annotated[
        bool,
        typer.Option("--break-glass/--no-break-glass"),
    ] = False,
) -> None:
    """Create and sign a preauthorization grant.

    Examples:
        autosd preauth create-grant --project-ids my-app --auto-deploy-prod --expires-in-hours 1
        autosd preauth create-grant --project-ids my-app --auto-heal --no-auto-deploy-prod
    """
    init_keys()
    private_key = load_private_key()
    scope = {
        "project_ids": project_ids or "*",
        "domains": [],
        "platforms": [],
    }
    capabilities = {
        "auto_push": auto_push,
        "auto_merge_pr": auto_merge_pr,
        "auto_deploy_dev": auto_deploy_dev,
        "auto_deploy_staging": auto_deploy_staging,
        "auto_deploy_prod": auto_deploy_prod,
        "auto_rollback": auto_rollback,
        "auto_heal": auto_heal,
        "create_repos": create_repos,
        "rotate_deployments": rotate_deployments,
        "publish_app_store": publish_app_store,
    }
    required_gates = {
        "quality_gates": True,
        "security_scan_mode": "if-available",
        "sbom": "if-available",
        "dependency_audit": "if-available",
        "canary_required_for_prod": True,
        "min_test_scope": "suite",
    }
    budgets = {
        "max_deploys_per_day": 20,
        "max_patches_per_incident": 3,
        "max_auto_merges_per_day": 10,
        "max_failures_before_halt": 5,
    }
    telemetry = {
        "allowed_modes": ["off", "anonymous", "minimal", "custom"],
        "retention_max_days": 30,
        "event_allowlist_ref": "default",
    }
    grant = create_grant(
        issuer=issuer,
        scope=scope,
        capabilities=capabilities,
        required_gates=required_gates,
        budgets=budgets,
        telemetry=telemetry,
        expires_in_hours=expires_in_hours,
        break_glass=break_glass,
        private_key=private_key,
    )
    output_path = save_grant(grant)
    console.print(f"Grant created: {grant.grant_id}")
    console.print(f"Path: {output_path}")


@preauth_app.command("list")
def preauth_list(
    active_only: Annotated[
        bool,
        typer.Option(
            "--active-only/--include-expired",
            help="Only show active (non-expired, non-revoked) grants.",
        ),
    ] = False,
) -> None:
    """List available signed grants.

    Example:
        autosd preauth list --active-only
    """
    grants = list_grants()
    if not grants:
        console.print("No grants found.")
        return
    revoked_ids = load_revoked_ids()
    table = Table(title="Preauth Grants")
    table.add_column("Grant ID")
    table.add_column("Issuer")
    table.add_column("Expires")
    table.add_column("Break Glass")
    table.add_column("Status")
    rows_added = 0
    for grant in grants:
        if active_only and (grant.grant_id in revoked_ids or grant.is_expired()):
            continue
        payload = grant.to_dict()
        status = "active"
        if grant.grant_id in revoked_ids:
            status = "revoked"
        elif grant.is_expired():
            status = "expired"
        table.add_row(
            grant.grant_id,
            str(payload.get("issuer", "")),
            str(payload.get("expires_at", "")),
            "yes" if bool(payload.get("break_glass", False)) else "no",
            status,
        )
        rows_added += 1
    if rows_added == 0:
        console.print("No grants matched the selected filters.")
        return
    console.print(table)


@preauth_app.command("show")
def preauth_show(
    grant_id: Annotated[str, typer.Argument(help="Grant identifier.")],
) -> None:
    """Show one grant payload.

    Example:
        autosd preauth show <grant_id>
    """
    grant = load_grant(grant_id)
    if grant is None:
        raise typer.BadParameter(f"Grant '{grant_id}' not found.")
    console.print_json(json.dumps(grant.to_dict(), indent=2))


@preauth_app.command("revoke")
def preauth_revoke(
    grant_id: Annotated[str, typer.Argument(help="Grant identifier.")],
    reason: Annotated[str, typer.Option(help="Revocation reason.")] = "revoked",
) -> None:
    """Revoke a grant immediately.

    Example:
        autosd preauth revoke <grant_id> --reason "incident response"
    """
    revoke_grant(grant_id, reason=reason)
    console.print(f"Grant revoked: {grant_id}")
