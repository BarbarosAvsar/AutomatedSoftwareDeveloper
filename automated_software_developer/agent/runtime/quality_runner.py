"""Quality-gate execution helpers for orchestrator runtime."""

from __future__ import annotations

from automated_software_developer.agent.executor import CommandExecutor
from automated_software_developer.agent.filesystem import FileWorkspace
from automated_software_developer.agent.models import CommandResult
from automated_software_developer.agent.quality import (
    QualityGateCacheEntry,
    compute_quality_gate_fingerprint,
    load_quality_gate_cache,
    save_quality_gate_cache,
)


def run_quality_gate_commands(
    *,
    workspace: FileWorkspace,
    commands: list[str],
    executor: CommandExecutor,
    config_payload: dict[str, object],
) -> tuple[list[CommandResult], bool]:
    """Run quality gate commands with cache support."""
    if not commands:
        return [], False
    fingerprint = compute_quality_gate_fingerprint(
        workspace.base_dir,
        commands=commands,
        config=config_payload,
    )
    cache = load_quality_gate_cache(workspace.base_dir)
    if (
        cache is not None
        and cache.fingerprint == fingerprint
        and cache.commands == commands
        and cache.results
        and all(result.passed for result in cache.results)
    ):
        return mark_cached_results(cache.results), True

    results = executor.run_many(commands, cwd=workspace.base_dir)
    if results and all(result.passed for result in results):
        post_fingerprint = compute_quality_gate_fingerprint(
            workspace.base_dir,
            commands=commands,
            config=config_payload,
        )
        save_quality_gate_cache(
            workspace.base_dir,
            QualityGateCacheEntry(
                fingerprint=post_fingerprint,
                commands=commands,
                results=results,
            ),
        )
    return results, False


def mark_cached_results(results: list[CommandResult]) -> list[CommandResult]:
    """Annotate cached command results for visibility."""
    cached_results: list[CommandResult] = []
    for item in results:
        note = "cached: previous success\n"
        stdout = item.stdout
        if note not in stdout:
            stdout = f"{note}{stdout}".strip()
        cached_results.append(
            CommandResult(
                command=item.command,
                exit_code=item.exit_code,
                stdout=stdout,
                stderr=item.stderr,
                duration_seconds=item.duration_seconds,
            )
        )
    return cached_results


def serialize_gate_results(
    *,
    results: list[CommandResult],
    reproducible: bool,
) -> list[dict[str, object]]:
    """Serialize gate results for provenance reporting."""
    duration_override = 0.0 if reproducible else None
    output: list[dict[str, object]] = []
    for item in results:
        duration = duration_override if duration_override is not None else item.duration_seconds
        output.append(
            {
                "command": item.command,
                "exit_code": item.exit_code,
                "duration_seconds": duration,
            }
        )
    return output
