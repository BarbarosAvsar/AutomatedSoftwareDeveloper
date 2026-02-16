"""Command-line interface bootstrap for the autonomous software development agent."""

from __future__ import annotations

# ruff: noqa: I001
from automated_software_developer.commands.common import app

# Import command modules for side-effect registration.
from automated_software_developer.commands import (  # noqa: F401
    agile,
    ci_plugins_ui,
    ops_release,
    preauth_policy,
    projects,
    run_and_verify,
    telemetry_incidents,
)

__all__ = ["app"]


if __name__ == "__main__":
    app()
