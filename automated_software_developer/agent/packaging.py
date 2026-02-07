"""Packaging/build planning and optional execution stage."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from automated_software_developer.agent.executor import CommandExecutor
from automated_software_developer.agent.models import CommandResult
from automated_software_developer.agent.platforms.base import PlatformPlan


@dataclass(frozen=True)
class PackagingExecutionResult:
    """Result of optional packaging command execution."""

    executed: bool
    commands: list[str]
    results: list[CommandResult]


class PackagingOrchestrator:
    """Executes adapter-provided build/package commands when enabled."""

    def __init__(self, executor: CommandExecutor) -> None:
        """Initialize packaging orchestrator with command executor."""
        self.executor = executor

    def execute(
        self,
        *,
        plan: PlatformPlan,
        project_dir: Path,
        enabled: bool,
    ) -> PackagingExecutionResult:
        """Execute build and package commands if enabled; otherwise return plan-only result."""
        commands = [*plan.build_commands, *plan.package_commands]
        if not enabled:
            return PackagingExecutionResult(executed=False, commands=commands, results=[])
        results = self.executor.run_many(commands, cwd=project_dir)
        if results and results[-1].exit_code != 0:
            failed = results[-1]
            raise RuntimeError(
                f"Packaging command failed: {failed.command}\n"
                f"stdout: {failed.stdout.strip()}\n"
                f"stderr: {failed.stderr.strip()}"
            )
        return PackagingExecutionResult(executed=True, commands=commands, results=results)
