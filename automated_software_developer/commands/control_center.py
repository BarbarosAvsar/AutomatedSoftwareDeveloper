"""CLI command registrations for the local AutoSD Control Center."""

from __future__ import annotations

# mypy: ignore-errors
# ruff: noqa: B008,F403,F405,I001
from automated_software_developer.commands.common import *
from automated_software_developer.agent.control_center import serve_control_center


@app.command("control-center")
def control_center(
    host: Annotated[
        str,
        typer.Option(help="Host interface for local control center."),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        typer.Option(help="TCP port for local control center."),
    ] = 8787,
    log_file: Annotated[
        Path,
        typer.Option(help="Log file displayed in monitor log panel."),
    ] = Path("autosd.log"),
) -> None:
    """Serve a local browser-based UI for AutoSD onboarding, runs, and operations."""
    if port <= 0 or port > 65535:
        raise typer.BadParameter("port must be between 1 and 65535.")
    console.print(f"Serving AutoSD Control Center on http://{host}:{port}")
    serve_control_center(host=host, port=port, provider_factory=_create_provider, log_file=log_file)
