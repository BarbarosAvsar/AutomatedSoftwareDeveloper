"""CLI command registrations."""

from __future__ import annotations

# mypy: ignore-errors
# ruff: noqa: B008,F403,F405,I001
from automated_software_developer.commands.common import *

@projects_app.command("list")
def projects_list(
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
    include_archived: Annotated[
        bool,
        typer.Option("--include-archived/--exclude-archived"),
    ] = False,
) -> None:
    """List registered generated projects."""
    registry = _create_registry(registry_path)
    entries = registry.list_entries(include_archived=include_archived)
    table = Table(title="Project Portfolio")
    table.add_column("Project ID")
    table.add_column("Name")
    table.add_column("Platforms")
    table.add_column("Version")
    table.add_column("Health")
    table.add_column("Archived")
    if not entries:
        console.print("No projects registered.")
        return
    for entry in entries:
        table.add_row(
            entry.project_id,
            entry.name,
            ", ".join(entry.platforms),
            entry.current_version,
            entry.health_status,
            "yes" if entry.archived else "no",
        )
    console.print(table)


@projects_app.command("show")
def projects_show(
    project_id: Annotated[str, typer.Argument(help="Project ID or exact name.")],
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
) -> None:
    """Show detailed metadata for one project."""
    registry = _create_registry(registry_path)
    entry = registry.get(project_id)
    if entry is None:
        raise typer.BadParameter(f"Project '{project_id}' not found.")
    console.print_json(json.dumps(entry.to_dict(), indent=2))


@projects_app.command("status")
def projects_status(
    all_projects: Annotated[
        bool,
        typer.Option("--all", help="Include archived projects."),
    ] = False,
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
) -> None:
    """Show compact project health and CI status table."""
    registry = _create_registry(registry_path)
    rows = registry.status_rows(include_archived=all_projects)
    table = Table(title="Project Status")
    table.add_column("Project ID")
    table.add_column("Name")
    table.add_column("Version")
    table.add_column("Health")
    table.add_column("CI")
    table.add_column("Security")
    table.add_column("Halted")
    if not rows:
        console.print("No project statuses available.")
        return
    for row in rows:
        table.add_row(
            row["project_id"],
            row["name"],
            row["version"],
            row["health"],
            row["ci"],
            row["security"],
            row["halted"],
        )
    console.print(table)


@projects_app.command("open")
def projects_open(
    project_id: Annotated[str, typer.Argument(help="Project ID or exact name.")],
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
) -> None:
    """Print repository URL and key metadata for one project."""
    registry = _create_registry(registry_path)
    entry = registry.get(project_id)
    if entry is None:
        raise typer.BadParameter(f"Project '{project_id}' not found.")
    payload = {
        "project_id": entry.project_id,
        "name": entry.name,
        "repo_url": entry.repo_url or "<none>",
        "default_branch": entry.default_branch,
        "current_version": entry.current_version,
    }
    console.print_json(json.dumps(payload, indent=2))


@projects_app.command("retire")
def projects_retire(
    project_id: Annotated[str, typer.Argument(help="Project ID or exact name.")],
    reason: Annotated[
        str,
        typer.Option(help="Retirement reason stored in project metadata."),
    ] = "retired by operator",
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
) -> None:
    """Retire one project and disable automation by default."""
    registry = _create_registry(registry_path)
    updated = registry.retire(project_id, reason=reason)
    console.print(
        f"Project '{updated.project_id}' retired. automation_halted={updated.automation_halted}"
    )



@dashboard_app.command("serve")
def dashboard_serve(
    host: Annotated[
        str,
        typer.Option(help="Host interface for local dashboard API."),
    ] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="TCP port for local dashboard API.")] = 8765,
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
) -> None:
    """Serve read-only local portfolio dashboard API."""
    if port <= 0 or port > 65535:
        raise typer.BadParameter("port must be between 1 and 65535.")
    registry = _create_registry(registry_path)
    console.print(f"Serving dashboard on http://{host}:{port}")
    serve_dashboard(registry=registry, host=host, port=port)
