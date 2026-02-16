"""CLI command registrations."""

from __future__ import annotations

# mypy: ignore-errors
# ruff: noqa: B008,F403,F405,I001
from automated_software_developer.commands.common import *


@telemetry_app.command("enable")
def telemetry_enable(
    project: Annotated[str, typer.Option(help="Project ID or exact name.")],
    mode: Annotated[
        str,
        typer.Option(help="Telemetry mode: off, anonymous, minimal, custom."),
    ] = "anonymous",
    retention_days: Annotated[
        int,
        typer.Option(help="Telemetry retention period in days."),
    ] = 30,
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
) -> None:
    """Enable or disable privacy-safe telemetry policy for a project.

    Examples:
        autosd telemetry enable --project my-app --mode anonymous --retention-days 30
        autosd telemetry enable --project my-app --mode off
    """
    policy = TelemetryPolicy.from_mode(mode, retention_days=retention_days)
    registry = _create_registry(registry_path)
    entry = registry.get(project)
    if entry is None:
        raise typer.BadParameter(f"Project '{project}' not found.")
    updated = registry.update(
        entry.project_id,
        telemetry_policy=policy.mode,
        data_retention_policy=f"{policy.retention_days}d",
    )
    project_dir = _resolve_project_path(updated.metadata)
    if project_dir is not None:
        _write_privacy_note(project_dir, policy)
    console.print(
        f"Telemetry policy for '{updated.project_id}' set to {policy.mode} "
        f"with {policy.retention_days}d retention."
    )


@telemetry_app.command("report")
def telemetry_report(
    project: Annotated[str, typer.Option(help="Project ID or exact name.")],
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
) -> None:
    """Ingest local telemetry events and print aggregate report for one project.

    Example:
        autosd telemetry report --project my-app
    """
    registry = _create_registry(registry_path)
    entry = registry.get(project)
    if entry is None:
        raise typer.BadParameter(f"Project '{project}' not found.")
    retention_days = _parse_retention_days(entry.data_retention_policy)
    policy = TelemetryPolicy.from_mode(entry.telemetry_policy, retention_days=retention_days)
    if policy.mode == "off":
        console.print(f"Telemetry is disabled for '{entry.project_id}'.")
        return
    project_dir = _resolve_project_path(entry.metadata)
    if project_dir is None:
        raise typer.BadParameter(
            f"Project '{entry.project_id}' has no local path metadata for telemetry ingestion."
        )
    events_path = _telemetry_events_path(project_dir)
    store = TelemetryStore()
    ingested = store.ingest_events_file(
        project_id=entry.project_id,
        events_path=events_path,
        policy=policy,
    )
    deleted = store.enforce_retention(policy.retention_days)
    report = store.report_project(entry.project_id)
    table = Table(title=f"Telemetry Report: {entry.project_id}")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Events Ingested", str(ingested))
    table.add_row("Events Pruned", str(deleted))
    table.add_row("Total Events", str(report.event_count))
    table.add_row("Error Events", str(report.error_events))
    table.add_row("Crash Events", str(report.crash_events))
    table.add_row("Average Value", f"{report.avg_value:.4f}")
    console.print(table)


@telemetry_app.command("report-all")
def telemetry_report_all(
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
    domain: Annotated[
        str | None,
        typer.Option(help="Optional exact domain filter."),
    ] = None,
    platform: Annotated[
        str | None,
        typer.Option(help="Optional platform filter."),
    ] = None,
) -> None:
    """Ingest and report telemetry for all registered projects with telemetry enabled.

    Example:
        autosd telemetry report-all --domain commerce
    """
    registry = _create_registry(registry_path)
    entries = registry.list_entries(include_archived=False)
    store = TelemetryStore()
    reports: list[tuple[str, int, int, int, float]] = []
    for entry in entries:
        if domain is not None and entry.domain != domain:
            continue
        if platform is not None and platform not in entry.platforms:
            continue
        retention_days = _parse_retention_days(entry.data_retention_policy)
        policy = TelemetryPolicy.from_mode(entry.telemetry_policy, retention_days=retention_days)
        if policy.mode == "off":
            continue
        project_dir = _resolve_project_path(entry.metadata)
        if project_dir is None:
            continue
        events_path = _telemetry_events_path(project_dir)
        store.ingest_events_file(
            project_id=entry.project_id,
            events_path=events_path,
            policy=policy,
        )
        store.enforce_retention(policy.retention_days)
        report = store.report_project(entry.project_id)
        reports.append(
            (
                report.project_id,
                report.event_count,
                report.error_events,
                report.crash_events,
                report.avg_value,
            )
        )
    if not reports:
        console.print("No telemetry reports available for selected projects.")
        return
    table = Table(title="Telemetry Reports")
    table.add_column("Project")
    table.add_column("Events")
    table.add_column("Errors")
    table.add_column("Crashes")
    table.add_column("Avg Value")
    for project_id, events, errors, crashes, avg_value in reports:
        table.add_row(project_id, str(events), str(errors), str(crashes), f"{avg_value:.4f}")
    console.print(table)


@incidents_app.command("list")
def incidents_list(
    project: Annotated[
        str | None,
        typer.Option(help="Optional project ID filter."),
    ] = None,
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
    incidents_path: Annotated[
        Path | None,
        typer.Option(help="Optional incidents JSONL path override."),
    ] = None,
) -> None:
    """List incidents from append-only incident ledger.

    Example:
        autosd incidents list --project my-app
    """
    engine = _create_incident_engine(registry_path=registry_path, incidents_path=incidents_path)
    records = engine.list_incidents(project_id=project)
    if not records:
        console.print("No incidents found.")
        return
    table = Table(title="Incidents")
    table.add_column("Incident")
    table.add_column("Project")
    table.add_column("Status")
    table.add_column("Severity")
    table.add_column("Source")
    for record in records:
        table.add_row(
            record.incident_id,
            record.project_id,
            record.status,
            record.severity,
            record.source,
        )
    console.print(table)


@incidents_app.command("show")
def incidents_show(
    incident_id: Annotated[str, typer.Argument(help="Incident identifier.")],
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
    incidents_path: Annotated[
        Path | None,
        typer.Option(help="Optional incidents JSONL path override."),
    ] = None,
) -> None:
    """Show one incident record.

    Example:
        autosd incidents show <incident_id>
    """
    engine = _create_incident_engine(registry_path=registry_path, incidents_path=incidents_path)
    incident = engine.get_incident(incident_id)
    if incident is None:
        raise typer.BadParameter(f"Incident '{incident_id}' not found.")
    console.print_json(json.dumps(incident.to_dict(), indent=2))


@app.command("heal")
def heal_project(
    project: Annotated[str, typer.Option(help="Project ID or exact name.")],
    incident: Annotated[
        str | None,
        typer.Option(help="Optional existing incident ID."),
    ] = None,
    target: Annotated[
        str | None,
        typer.Option(
            "--target",
            help="Optional deployment target after patch (docker/github_pages/generic_container).",
        ),
    ] = None,
    env: Annotated[
        str,
        typer.Option("--env", help="Deployment environment when target is provided."),
    ] = "staging",
    auto_push: Annotated[
        bool,
        typer.Option("--auto-push/--no-auto-push", help="Push healing patch branch."),
    ] = False,
    execute_deploy: Annotated[
        bool,
        typer.Option(
            "--execute-deploy/--scaffold-deploy",
            help="Execute deploy target commands when possible.",
        ),
    ] = False,
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
    incidents_path: Annotated[
        Path | None,
        typer.Option(help="Optional incidents JSONL path override."),
    ] = None,
    require_preauth: Annotated[
        bool,
        typer.Option("--require-preauth", help="Require valid preauthorization grant."),
    ] = False,
    preauth_grant: Annotated[
        str | None,
        typer.Option("--preauth-grant", help="Grant ID used for healing authorization."),
    ] = None,
) -> None:
    """Run incident-driven self-healing (patch -> optional deploy -> postmortem).

    Example:
        autosd heal --project my-app --target generic_container --env staging
    """
    registry = _create_registry(registry_path)
    entry = registry.get(project)
    if entry is None:
        raise typer.BadParameter(f"Project '{project}' not found.")
    required_capability = "auto_heal" if (require_preauth or preauth_grant is not None) else None
    grant = _resolve_verified_grant(
        grant_id=preauth_grant,
        require_preauth=require_preauth,
        required_capability=required_capability,
        project_id=entry.project_id,
        environment=env if target is not None else None,
    )
    project_dir = _resolve_project_path(entry.metadata)
    if grant is not None and project_dir is not None:
        ensure_project_grant_reference(project_dir, grant.grant_id)
    policy = resolve_effective_policy(project_policy=None, grant=grant)
    if project_dir is not None:
        _write_policy_snapshot(project_dir, policy.to_dict())
    if auto_push:
        push_decision = evaluate_action(policy=policy, action="auto_push")
        if not push_decision.allowed:
            raise typer.BadParameter(f"Policy blocked heal auto-push: {push_decision.reason}")
    if target is not None:
        deploy_decision = evaluate_action(policy=policy, action="deploy", environment=env)
        if not deploy_decision.allowed:
            raise typer.BadParameter(f"Policy blocked heal deploy: {deploy_decision.reason}")
    engine = _create_incident_engine(registry_path=registry_path, incidents_path=incidents_path)
    try:
        result = engine.heal_project(
            project_ref=entry.project_id,
            incident_id=incident,
            auto_push=auto_push,
            deploy_target=target,
            environment=env,
            execute_deploy=execute_deploy,
        )
    except (KeyError, ValueError) as exc:
        raise typer.BadParameter(str(exc.args[0])) from exc
    table = Table(title="Heal Result")
    table.add_column("Incident")
    table.add_column("Project")
    table.add_column("Status")
    table.add_column("Patch")
    table.add_column("Deploy")
    table.add_row(
        result.incident.incident_id,
        result.incident.project_id,
        result.incident.status,
        "ok" if result.patch_outcome.success else "failed",
        "n/a"
        if result.deploy_outcome is None
        else ("ok" if result.deploy_outcome.success else "failed"),
    )
    console.print(table)
    if result.incident.postmortem_path is not None:
        console.print(f"Postmortem: {result.incident.postmortem_path}")
    AuditLogger().log(
        project_id=entry.project_id,
        action="heal",
        result="success" if result.incident.status == "resolved" else "failed",
        grant_id=grant.grant_id if grant is not None else None,
        gates_run=["patch", "deploy" if target else "patch_only"],
        commit_ref=result.patch_outcome.commit_sha,
        tag_ref=None,
        break_glass_used=grant_break_glass(grant),
        details={
            "incident_id": result.incident.incident_id,
            "deploy_target": target,
            "environment": env,
        },
    )
    if result.incident.status != "resolved":
        raise typer.Exit(code=1)
