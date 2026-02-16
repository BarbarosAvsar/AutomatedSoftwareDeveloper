"""CLI command registrations."""

from __future__ import annotations

# mypy: ignore-errors
# ruff: noqa: B008,F403,F405,I001
from automated_software_developer.commands.common import *


@app.command("halt")
def halt_project(
    project: Annotated[str, typer.Option(help="Project ID or exact name.")],
    reason: Annotated[
        str,
        typer.Option(help="Reason recorded in project metadata."),
    ] = "manual halt",
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
) -> None:
    """Halt autonomous actions for a project (kill switch)."""
    registry = _create_registry(registry_path)
    entry = registry.get(project)
    if entry is None:
        raise typer.BadParameter(f"Project '{project}' not found.")
    metadata = dict(entry.metadata)
    metadata["halt_reason"] = reason
    metadata["halted_at"] = datetime.now(tz=UTC).isoformat()
    registry.update(entry.project_id, automation_halted=True, metadata=metadata)
    console.print(f"Automation halted for '{entry.project_id}'.")


@app.command("resume")
def resume_project(
    project: Annotated[str, typer.Option(help="Project ID or exact name.")],
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
) -> None:
    """Resume autonomous actions for a halted project."""
    registry = _create_registry(registry_path)
    entry = registry.get(project)
    if entry is None:
        raise typer.BadParameter(f"Project '{project}' not found.")
    metadata = dict(entry.metadata)
    metadata["resumed_at"] = datetime.now(tz=UTC).isoformat()
    registry.update(entry.project_id, automation_halted=False, metadata=metadata)
    console.print(f"Automation resumed for '{entry.project_id}'.")


@app.command("patch")
def patch_project(
    project: Annotated[str, typer.Option(help="Project ID or exact name.")],
    reason: Annotated[str, typer.Option(help="Patch reason for changelog/commit.")] = "maintenance",
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
    auto_push: Annotated[
        bool,
        typer.Option("--auto-push/--no-auto-push", help="Push patch branch to origin."),
    ] = False,
    create_tag: Annotated[
        bool,
        typer.Option("--create-tag/--no-create-tag", help="Create version tag for patch."),
    ] = True,
    require_preauth: Annotated[
        bool,
        typer.Option("--require-preauth", help="Require valid preauthorization grant."),
    ] = False,
    preauth_grant: Annotated[
        str | None,
        typer.Option("--preauth-grant", help="Grant ID used for privileged patch actions."),
    ] = None,
) -> None:
    """Run patch workflow for a single project.

    Examples:
        autosd patch --project my-app --reason "security fix"
        autosd patch --project my-app --auto-push --preauth-grant <grant_id>
    """
    if not project.strip():
        raise typer.BadParameter("project must be non-empty.")
    registry = _create_registry(registry_path)
    entry = registry.get(project)
    if entry is None:
        raise typer.BadParameter(f"Project '{project}' not found.")
    required_capability = "auto_push" if auto_push else None
    grant = _resolve_verified_grant(
        grant_id=preauth_grant,
        require_preauth=require_preauth or (auto_push and preauth_grant is None),
        required_capability=required_capability,
        project_id=entry.project_id,
        environment=None,
    )
    project_dir = _resolve_project_path(entry.metadata)
    if grant is not None and project_dir is not None:
        ensure_project_grant_reference(project_dir, grant.grant_id)
    policy = resolve_effective_policy(project_policy=None, grant=grant)
    if project_dir is not None:
        _write_policy_snapshot(project_dir, policy.to_dict())
    if auto_push:
        decision = evaluate_action(policy=policy, action="auto_push")
        if not decision.allowed:
            raise typer.BadParameter(f"Policy blocked action: {decision.reason}")
    engine = PatchEngine(registry=registry)
    outcome = engine.patch_project(
        entry.project_id,
        reason=reason,
        auto_push=auto_push,
        create_tag=create_tag,
    )
    table = Table(title="Patch Result")
    table.add_column("Project")
    table.add_column("Status")
    table.add_column("Branch")
    table.add_column("Version")
    table.add_column("Commit")
    table.add_row(
        outcome.project_id,
        "ok" if outcome.success else "failed",
        outcome.branch or "-",
        f"{outcome.old_version} -> {outcome.new_version or '-'}",
        outcome.commit_sha or "-",
    )
    console.print(table)
    AuditLogger().log(
        project_id=entry.project_id,
        action="patch",
        result="success" if outcome.success else "failed",
        grant_id=grant.grant_id if grant is not None else None,
        gates_run=["quality_gates", "version_bump"],
        commit_ref=outcome.commit_sha,
        tag_ref=(
            f"v{outcome.new_version}" if outcome.new_version is not None and create_tag else None
        ),
        break_glass_used=grant_break_glass(grant),
        details={"reason": reason, "branch": outcome.branch},
    )
    if outcome.error is not None:
        raise typer.Exit(code=1)


@app.command("patch-all")
def patch_all_projects(
    reason: Annotated[str, typer.Option(help="Patch reason for changelog/commit.")] = "maintenance",
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
    domain: Annotated[
        str | None,
        typer.Option(help="Filter by exact project domain."),
    ] = None,
    platform: Annotated[
        str | None,
        typer.Option(help="Filter by platform identifier."),
    ] = None,
    needs_security: Annotated[
        bool,
        typer.Option(help="Only projects with non-green security status."),
    ] = False,
    needs_upgrade: Annotated[
        bool,
        typer.Option(help="Only projects with metadata.needs_upgrade=true."),
    ] = False,
    telemetry_enabled: Annotated[
        bool,
        typer.Option(help="Only projects with telemetry enabled."),
    ] = False,
    deployed: Annotated[
        bool,
        typer.Option(help="Only projects with at least one deploy record."),
    ] = False,
    auto_push: Annotated[
        bool,
        typer.Option("--auto-push/--no-auto-push", help="Push patch branches to origin."),
    ] = False,
    create_tag: Annotated[
        bool,
        typer.Option("--create-tag/--no-create-tag", help="Create version tags for patches."),
    ] = True,
    require_preauth: Annotated[
        bool,
        typer.Option("--require-preauth", help="Require valid preauthorization grant."),
    ] = False,
    preauth_grant: Annotated[
        str | None,
        typer.Option("--preauth-grant", help="Grant ID used for privileged patch actions."),
    ] = None,
) -> None:
    """Run patch workflow for all projects matching filters.

    Example:
        autosd patch-all --domain commerce --needs-upgrade --reason "dependency refresh"
    """
    registry = _create_registry(registry_path)
    required_capability = "auto_push" if auto_push else None
    grant = _resolve_verified_grant(
        grant_id=preauth_grant,
        require_preauth=require_preauth or (auto_push and preauth_grant is None),
        required_capability=required_capability,
        project_id=None,
        environment=None,
    )
    policy = resolve_effective_policy(project_policy=None, grant=grant)
    if auto_push:
        decision = evaluate_action(policy=policy, action="auto_push")
        if not decision.allowed:
            raise typer.BadParameter(f"Policy blocked action: {decision.reason}")
    engine = PatchEngine(registry=registry)
    filters = PatchFilters(
        domain=domain,
        platform=platform,
        needs_security=needs_security,
        needs_upgrade=needs_upgrade,
        telemetry_enabled=telemetry_enabled,
        deployed=deployed,
    )
    outcomes = engine.patch_all(
        reason=reason,
        filters=filters,
        auto_push=auto_push,
        create_tag=create_tag,
    )
    table = Table(title="Patch-All Results")
    table.add_column("Project")
    table.add_column("Status")
    table.add_column("Version")
    table.add_column("Pending Push")
    if not outcomes:
        console.print("No projects matched the selected filters.")
        return
    failures = 0
    for outcome in outcomes:
        if not outcome.success:
            failures += 1
        AuditLogger().log(
            project_id=outcome.project_id,
            action="patch_all_item",
            result="success" if outcome.success else "failed",
            grant_id=grant.grant_id if grant is not None else None,
            gates_run=["quality_gates", "version_bump"],
            commit_ref=outcome.commit_sha,
            tag_ref=(
                f"v{outcome.new_version}"
                if outcome.new_version is not None and create_tag
                else None
            ),
            break_glass_used=grant_break_glass(grant),
            details={"reason": reason, "branch": outcome.branch},
        )
        table.add_row(
            outcome.project_id,
            "ok" if outcome.success else "failed",
            f"{outcome.old_version} -> {outcome.new_version or '-'}",
            "yes" if outcome.pending_push else "no",
        )
    console.print(table)
    if failures > 0:
        raise typer.Exit(code=1)


@app.command("deploy")
def deploy_project(
    project: Annotated[str, typer.Option(help="Project ID or exact name.")],
    env: Annotated[
        str,
        typer.Option("--env", help="Target environment: dev, staging, or prod."),
    ] = "dev",
    target: Annotated[
        str,
        typer.Option(
            "--target",
            help="Deployment target (docker, github_pages, generic_container).",
        ),
    ] = "generic_container",
    strategy: Annotated[
        str,
        typer.Option(help="Deployment strategy: standard, canary, blue-green."),
    ] = "standard",
    execute: Annotated[
        bool,
        typer.Option(
            "--execute/--scaffold-only",
            help="Run target commands when possible; default is scaffold-only.",
        ),
    ] = False,
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
    require_preauth: Annotated[
        bool,
        typer.Option("--require-preauth", help="Require valid preauthorization grant."),
    ] = False,
    preauth_grant: Annotated[
        str | None,
        typer.Option("--preauth-grant", help="Grant ID used for privileged deploy actions."),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", help="Skip confirmation prompt for destructive actions."),
    ] = False,
) -> None:
    """Deploy one project to selected target/environment.

    Examples:
        autosd deploy --project my-app --env staging --target generic_container
        autosd deploy --project my-app --env prod --target docker --preauth-grant <grant_id>
    """
    registry = _create_registry(registry_path)
    entry = registry.get(project)
    if entry is None:
        raise typer.BadParameter(f"Project '{project}' not found.")
    env_normalized = env.strip().lower()
    capability_by_env = {
        "dev": "auto_deploy_dev",
        "staging": "auto_deploy_staging",
        "prod": "auto_deploy_prod",
    }
    required_capability = capability_by_env.get(env_normalized)
    if required_capability is None:
        raise _cli_error(
            "AUTOSD-ENV-INVALID",
            "env must be one of: dev, staging, prod",
            "Use --env dev|staging|prod.",
        )
    grant = _resolve_verified_grant(
        grant_id=preauth_grant,
        require_preauth=require_preauth or (env_normalized == "prod"),
        required_capability=required_capability,
        project_id=entry.project_id,
        environment=env_normalized,
    )
    project_dir = _resolve_project_path(entry.metadata)
    if grant is not None and project_dir is not None:
        ensure_project_grant_reference(project_dir, grant.grant_id)
    policy = resolve_effective_policy(project_policy=None, grant=grant)
    if project_dir is not None:
        _write_policy_snapshot(project_dir, policy.to_dict())
    decision = evaluate_action(policy=policy, action="deploy", environment=env_normalized)
    if not decision.allowed:
        raise typer.BadParameter(f"Policy blocked deploy action: {decision.reason}")
    if env_normalized == "prod":
        _confirm_destructive_action(
            f"Confirm production deploy for '{entry.project_id}' to {target}? ",
            force=force,
        )
    orchestrator = _create_deployment_orchestrator(registry_path)
    try:
        result = orchestrator.deploy(
            project_ref=entry.project_id,
            environment=env_normalized,
            target=target,
            strategy=strategy,
            execute=execute,
        )
    except KeyError as exc:
        raise typer.BadParameter(str(exc.args[0])) from exc
    table = Table(title="Deploy Result")
    table.add_column("Project")
    table.add_column("Target")
    table.add_column("Env")
    table.add_column("Version")
    table.add_column("Status")
    table.add_row(
        result.project_id,
        result.target,
        result.environment,
        result.version,
        "[green]ok[/green]" if result.success else "[red]failed[/red]",
    )
    console.print(table)
    console.print(result.message)
    AuditLogger().log(
        project_id=entry.project_id,
        action="deploy",
        result="success" if result.success else "failed",
        grant_id=grant.grant_id if grant is not None else None,
        gates_run=["deployment_policy", "target_scaffold"],
        commit_ref=None,
        tag_ref=None,
        break_glass_used=grant_break_glass(grant),
        details={
            "environment": env_normalized,
            "target": target,
            "strategy": strategy,
            "scaffold_only": result.scaffold_only,
        },
    )
    if not result.success:
        raise typer.Exit(code=1)


@app.command("rollback")
def rollback_project(
    project: Annotated[str, typer.Option(help="Project ID or exact name.")],
    env: Annotated[str, typer.Option("--env", help="Target environment.")] = "dev",
    target: Annotated[
        str,
        typer.Option(
            "--target",
            help="Deployment target (docker, github_pages, generic_container).",
        ),
    ] = "generic_container",
    execute: Annotated[
        bool,
        typer.Option(
            "--execute/--scaffold-only",
            help="Run rollback commands when possible; default is scaffold-only.",
        ),
    ] = False,
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
    require_preauth: Annotated[
        bool,
        typer.Option("--require-preauth", help="Require valid preauthorization grant."),
    ] = False,
    preauth_grant: Annotated[
        str | None,
        typer.Option("--preauth-grant", help="Grant ID used for rollback authorization."),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", help="Skip confirmation prompt for destructive actions."),
    ] = False,
) -> None:
    """Rollback one project deployment.

    Example:
        autosd rollback --project my-app --env staging --target generic_container
    """
    registry = _create_registry(registry_path)
    entry = registry.get(project)
    if entry is None:
        raise typer.BadParameter(f"Project '{project}' not found.")
    grant = _resolve_verified_grant(
        grant_id=preauth_grant,
        require_preauth=require_preauth,
        required_capability="auto_rollback" if preauth_grant is not None else None,
        project_id=entry.project_id,
        environment=env,
    )
    project_dir = _resolve_project_path(entry.metadata)
    if grant is not None and project_dir is not None:
        ensure_project_grant_reference(project_dir, grant.grant_id)
    _confirm_destructive_action(
        f"Confirm rollback for '{entry.project_id}' in {env} on {target}? ",
        force=force,
    )
    orchestrator = _create_deployment_orchestrator(registry_path)
    try:
        result = orchestrator.rollback(
            project_ref=entry.project_id,
            environment=env,
            target=target,
            execute=execute,
        )
    except KeyError as exc:
        raise typer.BadParameter(str(exc.args[0])) from exc
    console.print(
        "Rollback "
        f"{result.target}/{result.environment}: "
        f"{'[green]ok[/green]' if result.success else '[red]failed[/red]'}"
    )
    console.print(result.message)
    AuditLogger().log(
        project_id=entry.project_id,
        action="rollback",
        result="success" if result.success else "failed",
        grant_id=grant.grant_id if grant is not None else None,
        gates_run=["rollback_marker"],
        commit_ref=None,
        tag_ref=None,
        break_glass_used=grant_break_glass(grant),
        details={"environment": env, "target": target},
    )
    if not result.success:
        raise typer.Exit(code=1)


@app.command("promote")
def promote_project(
    project: Annotated[str, typer.Option(help="Project ID or exact name.")],
    from_env: Annotated[
        str,
        typer.Option("--from", help="Source environment."),
    ] = "staging",
    to_env: Annotated[
        str,
        typer.Option("--to", help="Target environment."),
    ] = "prod",
    target: Annotated[
        str,
        typer.Option(
            "--target",
            help="Deployment target (docker, github_pages, generic_container).",
        ),
    ] = "generic_container",
    execute: Annotated[
        bool,
        typer.Option(
            "--execute/--scaffold-only",
            help="Run promotion commands when possible; default is scaffold-only.",
        ),
    ] = False,
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
    require_preauth: Annotated[
        bool,
        typer.Option("--require-preauth", help="Require valid preauthorization grant."),
    ] = False,
    preauth_grant: Annotated[
        str | None,
        typer.Option("--preauth-grant", help="Grant ID used for promotion authorization."),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", help="Skip confirmation prompt for destructive actions."),
    ] = False,
) -> None:
    """Promote one project from staging to production-like environment.

    Example:
        autosd promote --project my-app --from staging --to prod --target generic_container
    """
    registry = _create_registry(registry_path)
    entry = registry.get(project)
    if entry is None:
        raise typer.BadParameter(f"Project '{project}' not found.")
    target_env = to_env.strip().lower()
    capability_by_env = {
        "dev": "auto_deploy_dev",
        "staging": "auto_deploy_staging",
        "prod": "auto_deploy_prod",
    }
    required_capability = capability_by_env.get(target_env)
    if required_capability is None:
        raise _cli_error(
            "AUTOSD-TARGET-ENV-INVALID",
            "--to must be one of: dev, staging, prod",
            "Use --to dev|staging|prod.",
        )
    grant = _resolve_verified_grant(
        grant_id=preauth_grant,
        require_preauth=require_preauth or (target_env == "prod"),
        required_capability=required_capability,
        project_id=entry.project_id,
        environment=target_env,
    )
    project_dir = _resolve_project_path(entry.metadata)
    if grant is not None and project_dir is not None:
        ensure_project_grant_reference(project_dir, grant.grant_id)
    policy = resolve_effective_policy(project_policy=None, grant=grant)
    if project_dir is not None:
        _write_policy_snapshot(project_dir, policy.to_dict())
    decision = evaluate_action(policy=policy, action="deploy", environment=target_env)
    if not decision.allowed:
        raise typer.BadParameter(f"Policy blocked promotion action: {decision.reason}")
    if target_env == "prod":
        _confirm_destructive_action(
            f"Confirm promotion for '{entry.project_id}' from {from_env} to {target_env}? ",
            force=force,
        )
    orchestrator = _create_deployment_orchestrator(registry_path)
    try:
        result = orchestrator.promote(
            project_ref=entry.project_id,
            source_environment=from_env,
            target_environment=target_env,
            target=target,
            execute=execute,
        )
    except KeyError as exc:
        raise typer.BadParameter(str(exc.args[0])) from exc
    console.print(
        "Promote "
        f"{from_env}->{target_env} on {target}: "
        f"{'[green]ok[/green]' if result.success else '[red]failed[/red]'}"
    )
    console.print(result.message)
    AuditLogger().log(
        project_id=entry.project_id,
        action="promote",
        result="success" if result.success else "failed",
        grant_id=grant.grant_id if grant is not None else None,
        gates_run=["deployment_policy", "promotion"],
        commit_ref=None,
        tag_ref=None,
        break_glass_used=grant_break_glass(grant),
        details={"from": from_env, "to": target_env, "target": target},
    )
    if not result.success:
        raise typer.Exit(code=1)


@app.command("release")
def release_project(
    project: Annotated[str, typer.Option(help="Project id or name.")],
    version: Annotated[str, typer.Option(help="Release version tag.")] = "0.1.0",
    tag: Annotated[str | None, typer.Option(help="Optional git tag name.")] = None,
    registry_path: Annotated[
        Path | None,
        typer.Option("--registry-path", help="Override portfolio registry path."),
    ] = None,
) -> None:
    """Create a release bundle under .autosd/releases/."""
    registry = _create_registry(registry_path)
    entry = registry.get(project)
    if entry is None:
        raise typer.BadParameter(f"Project '{project}' not found in registry.")
    project_dir = _resolve_project_path(entry.metadata)
    if project_dir is None:
        raise typer.BadParameter("Project path could not be resolved from registry metadata.")

    release_manager = ReleaseManager()
    bundle = release_manager.create_release(
        project_dir=project_dir,
        project_id=entry.project_id,
        version=version,
        tag=tag,
    )
    console.print("Release bundle created:")
    console.print(f"- release_id: {bundle.release_id}")
    console.print(f"- release_dir: {bundle.release_dir}")
    console.print(f"- manifest: {bundle.manifest_path}")
