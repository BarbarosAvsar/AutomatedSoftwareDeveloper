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
