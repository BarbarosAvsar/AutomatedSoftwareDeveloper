"""CLI command registrations."""

from __future__ import annotations

# mypy: ignore-errors
# ruff: noqa: B008,F403,F405,I001
from automated_software_developer.commands.common import *

@ci_app.command("mirror")
def ci_mirror(
    path: Annotated[
        Path,
        typer.Option("--path", help="Repository path to run the CI mirror against."),
    ] = Path("."),
) -> None:
    """Run the standardized CI entrypoint for a repository."""
    result = run_ci_mirror(path)
    status = "PASS" if result.passed else "FAIL"
    console.print(f"[{status}] {result.command} ({result.duration_seconds:.2f}s)")
    if not result.passed:
        raise typer.Exit(code=1)


@ci_app.command("lint-workflows")
def ci_lint_workflows(
    path: Annotated[
        Path,
        typer.Option("--path", help="Repository path containing workflows."),
    ] = Path("."),
) -> None:
    """Lint GitHub Actions workflows for safety and correctness."""
    results = lint_workflows(path)
    failed = [result for result in results if not result.passed]
    if failed:
        for result in failed:
            console.print(f"[FAIL] {result.path}: {', '.join(result.errors)}")
        raise typer.Exit(code=1)
    console.print("[PASS] All workflows linted successfully.")



@plugins_app.command("list")
def list_plugins() -> None:
    """List available plugins."""
    registry = PluginRegistry()
    table = Table(title="Available Plugins")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="magenta")
    table.add_column("Enabled", style="green")
    for plugin in registry.list_plugins():
        table.add_row(plugin.plugin_id, plugin.name, "yes" if plugin.enabled else "no")
    console.print(table)


@plugins_app.command("enable")
def enable_plugin(plugin_id: Annotated[str, typer.Argument(..., min=1)]) -> None:
    """Enable a plugin by id."""
    registry = PluginRegistry()
    plugin = registry.enable_plugin(plugin_id)
    console.print(f"Enabled plugin: {plugin.name}")


@plugins_app.command("disable")
def disable_plugin(plugin_id: Annotated[str, typer.Argument(..., min=1)]) -> None:
    """Disable a plugin by id."""
    registry = PluginRegistry()
    plugin = registry.disable_plugin(plugin_id)
    console.print(f"Disabled plugin: {plugin.name}")


@ui_app.command("serve")
def ui_serve(
    host: Annotated[
        str,
        typer.Option(help="Host interface for backend/frontend UI services."),
    ] = "127.0.0.1",
    backend_port: Annotated[
        int,
        typer.Option(help="Backend API port for FastAPI service."),
    ] = 8080,
    frontend_port: Annotated[
        int,
        typer.Option(help="Frontend Vite port for the React app."),
    ] = 5173,
    open_browser: Annotated[
        bool,
        typer.Option(
            "--open-browser/--no-open-browser",
            help="Open the frontend URL in the default browser once started.",
        ),
    ] = True,
    reload: Annotated[
        bool,
        typer.Option(
            "--reload/--no-reload",
            help="Enable uvicorn auto-reload for development workflows.",
        ),
    ] = True,
    install_frontend_deps: Annotated[
        bool,
        typer.Option(
            "--install-frontend-deps/--no-install-frontend-deps",
            help="Install frontend npm dependencies when ui/frontend/node_modules is missing.",
        ),
    ] = False,
) -> None:
    """Serve backend and frontend UI services together."""
    if backend_port < 1 or backend_port > 65535:
        raise typer.BadParameter("backend-port must be between 1 and 65535.")
    if frontend_port < 1 or frontend_port > 65535:
        raise typer.BadParameter("frontend-port must be between 1 and 65535.")

    config = UIServeConfig(
        host=host,
        backend_port=backend_port,
        frontend_port=frontend_port,
        open_browser=open_browser,
        reload=reload,
        install_frontend_deps=install_frontend_deps,
    )
    repo_root = Path(__file__).resolve().parent.parent
    try:
        serve_ui(config, repo_root=repo_root)
    except UICommandError as exc:
        raise typer.BadParameter(str(exc)) from exc


@ui_app.command("install-shortcuts")
def ui_install_shortcuts() -> None:
    """Install Windows desktop launch shortcuts for AutoSD UI."""
    repo_root = Path(__file__).resolve().parent.parent
    try:
        installed = install_windows_shortcuts(repo_root=repo_root)
    except UICommandError as exc:
        raise typer.BadParameter(str(exc)) from exc
    for path in installed:
        console.print(f"Installed: {path}")


@ui_app.command("remove-shortcuts")
def ui_remove_shortcuts() -> None:
    """Remove Windows desktop launch shortcuts for AutoSD UI."""
    try:
        removed = remove_windows_shortcuts()
    except UICommandError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if not removed:
        console.print("No AutoSD UI desktop shortcuts were present.")
        return
    for path in removed:
        console.print(f"Removed: {path}")
