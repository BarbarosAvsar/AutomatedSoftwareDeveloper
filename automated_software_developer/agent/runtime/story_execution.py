"""Story execution runtime helpers for the orchestrator."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from automated_software_developer.agent.backlog import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    StoryBacklog,
    resolve_story_commands,
)
from automated_software_developer.agent.executor import CommandExecutor
from automated_software_developer.agent.filesystem import FileWorkspace
from automated_software_developer.agent.journal import PromptJournal, hash_text
from automated_software_developer.agent.models import (
    BacklogStory,
    CommandResult,
    ExecutionBundle,
    PromptTemplate,
    StoryExecutionState,
)
from automated_software_developer.agent.prompts import (
    build_story_implementation_system_prompt,
    build_story_implementation_user_prompt,
)
from automated_software_developer.agent.providers.base import LLMProvider
from automated_software_developer.agent.quality import (
    QualityGateResult,
    build_quality_gate_plan,
    evaluate_python_quality,
)

ApplyOperationsFn = Callable[[ExecutionBundle, FileWorkspace], None]
AcceptanceCriteriaFn = Callable[[BacklogStory, FileWorkspace], bool]
QualityRunnerFn = Callable[[FileWorkspace, list[str]], tuple[list[CommandResult], bool]]


def execute_story_loop(
    *,
    story: BacklogStory,
    workspace: FileWorkspace,
    backlog: StoryBacklog,
    refined_markdown: str,
    repo_guidelines: str | None,
    template: PromptTemplate,
    journal: PromptJournal,
    prompt_seed: int | None,
    prefetched: Any | None,
    max_attempts: int,
    snapshot_max_files: int,
    snapshot_max_chars_per_file: int,
    provider: LLMProvider,
    executor: CommandExecutor,
    enforce_quality_gates: bool,
    enable_security_scan: bool,
    security_scan_mode: str,
    enforce_docstrings: bool,
    allow_stale_parallel_prompts: bool,
    apply_operations: ApplyOperationsFn,
    acceptance_criteria_satisfied: AcceptanceCriteriaFn,
    run_quality_gate_commands: QualityRunnerFn,
    now: Callable[[], str],
) -> StoryExecutionState:
    """Execute one story with bounded retries and journaling."""
    feedback: str | None = story.last_error
    last_results: list[CommandResult] = []
    default_commands = resolve_story_commands(story, backlog.global_verification_commands)

    for attempt in range(1, max_attempts + 1):
        snapshot = workspace.build_context_snapshot(
            max_files=snapshot_max_files,
            max_chars_per_file=snapshot_max_chars_per_file,
        )
        snapshot_hash = hash_text(snapshot)
        prefetch_snapshot_match: bool | None = None
        use_prefetch = (
            prefetched is not None
            and attempt == 1
            and (prefetched.snapshot_hash == snapshot_hash or allow_stale_parallel_prompts)
        )
        prefetched_data = prefetched if use_prefetch and prefetched is not None else None
        if prefetched_data is not None:
            system_prompt = prefetched_data.system_prompt
            user_prompt = prefetched_data.user_prompt
            prompt_fingerprint = prefetched_data.prompt_fingerprint
            prefetch_snapshot_match = prefetched_data.snapshot_hash == snapshot_hash
        else:
            system_prompt = build_story_implementation_system_prompt(template)
            user_prompt = build_story_implementation_user_prompt(
                refined_requirements_markdown=refined_markdown,
                story=story,
                project_snapshot=snapshot,
                fallback_verification_commands=backlog.global_verification_commands,
                previous_attempt_feedback=feedback,
                repo_guidelines=repo_guidelines,
            )
            prompt_fingerprint = hash_text(system_prompt + "\n" + user_prompt)
        raw_response: dict[str, Any] | None = None
        bundle: ExecutionBundle | None = None
        commands = default_commands
        error_text: str | None = None
        quality_warnings: list[str] = []
        quality_result_text: str | None = None
        quality_cached = False

        try:
            if prefetched_data is not None:
                raw_response = prefetched_data.response
            else:
                raw_response = provider.generate_json(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    seed=prompt_seed,
                )
            bundle = ExecutionBundle.from_dict(raw_response)
            apply_operations(bundle, workspace)
            quality_plan = build_quality_gate_plan(
                workspace.base_dir,
                enforce_quality_gates=enforce_quality_gates,
                enable_security_scan=enable_security_scan,
                security_scan_mode=security_scan_mode,
            )
            quality_warnings = quality_plan.warnings
            quality_commands = dedupe_commands(
                [*quality_plan.format_commands, *quality_plan.verification_commands]
            )
            quality_results, quality_cached = run_quality_gate_commands(workspace, quality_commands)
            verification_commands = dedupe_commands(
                list(bundle.verification_commands or default_commands)
            )
            commands = [*quality_commands, *verification_commands]
            if quality_results and not all(result.passed for result in quality_results):
                last_results = quality_results
            else:
                verification_results = executor.run_many(
                    verification_commands,
                    cwd=workspace.base_dir,
                )
                last_results = [*quality_results, *verification_results]

            static_quality = evaluate_python_quality(
                workspace.base_dir,
                enforce_docstrings=enforce_docstrings,
            )
            if not static_quality.passed:
                quality_result_text = format_quality_findings(static_quality)
        except Exception as exc:  # noqa: BLE001
            error_text = f"Story attempt failed before verification. Error: {exc}"
            last_results = []

        criteria_ok = acceptance_criteria_satisfied(story, workspace)
        commands_passed = bool(last_results) and all(result.passed for result in last_results)
        outcome = (
            "pass"
            if error_text is None
            and commands_passed
            and criteria_ok
            and quality_result_text is None
            else "fail"
        )
        unified_actions = build_unified_actions(
            bundle=bundle,
            verification_commands=commands,
            command_results=last_results,
            error_text=error_text,
            quality_result_text=quality_result_text,
            criteria_ok=criteria_ok,
        )
        failing_checks = None
        if outcome == "fail":
            failing_checks = summarize_unified_action_errors(unified_actions)
            feedback = failing_checks

        journal.append(
            {
                "timestamp": now(),
                "phase": "story_execution",
                "template_id": template.template_id,
                "template_version": template.version,
                "story_id": story.story_id,
                "story_title": story.title,
                "attempt": attempt,
                "model_settings": {
                    "provider": type(provider).__name__,
                    "seed": prompt_seed,
                },
                "prompt_fingerprint": prompt_fingerprint,
                "response_fingerprint": hash_text(json.dumps(raw_response, sort_keys=True))
                if raw_response is not None
                else None,
                "prefetch_used": use_prefetch,
                "prefetch_snapshot_match": prefetch_snapshot_match,
                "tool_actions_requested": [
                    {"op": item.op, "path": item.path}
                    for item in (bundle.operations if bundle is not None else [])
                ],
                "unified_actions": unified_actions,
                "verification_commands": commands,
                "outcome": outcome,
                "failing_checks": failing_checks,
                "error": error_text,
                "quality_warnings": quality_warnings,
                "quality_cache_hit": quality_cached,
                "fix_iteration": attempt - 1,
            }
        )

        if outcome == "pass":
            return StoryExecutionState(
                story_id=story.story_id,
                attempt=attempt,
                status=STATUS_COMPLETED,
                verification_results=last_results,
                error=None,
            )

    return StoryExecutionState(
        story_id=story.story_id,
        attempt=max_attempts,
        status=STATUS_FAILED,
        verification_results=last_results,
        error=feedback,
    )


def build_unified_actions(
    *,
    bundle: ExecutionBundle | None,
    verification_commands: list[str],
    command_results: list[CommandResult],
    error_text: str | None,
    quality_result_text: str | None,
    criteria_ok: bool,
) -> list[dict[str, Any]]:
    """Build one consolidated action timeline including inline error summaries."""
    actions: list[dict[str, Any]] = []
    for operation in bundle.operations if bundle is not None else []:
        actions.append(
            {
                "kind": "file_operation",
                "action": operation.op,
                "target": operation.path,
                "status": "applied",
                "error_summary": None,
            }
        )

    results_by_command = {result.command: result for result in command_results}
    for command in verification_commands:
        result = results_by_command.get(command)
        if result is None:
            actions.append(
                {
                    "kind": "verification_command",
                    "action": command,
                    "status": "not_executed",
                    "error_summary": error_text,
                }
            )
            continue

        error_summary: str | None = None
        if not result.passed:
            stderr = result.stderr.strip()
            stdout = result.stdout.strip()
            error_summary = stderr or stdout or f"Command exited with code {result.exit_code}."
        actions.append(
            {
                "kind": "verification_command",
                "action": command,
                "status": "passed" if result.passed else "failed",
                "error_summary": error_summary,
            }
        )

    if quality_result_text is not None:
        actions.append(
            {
                "kind": "quality_gate",
                "action": "python_static_quality",
                "status": "failed",
                "error_summary": quality_result_text,
            }
        )

    actions.append(
        {
            "kind": "acceptance_criteria",
            "action": "executable_checks",
            "status": "passed" if criteria_ok else "failed",
            "error_summary": (
                None if criteria_ok else "Executable acceptance criteria checks failed."
            ),
        }
    )

    if error_text is not None and not actions:
        actions.append(
            {
                "kind": "execution",
                "action": "story_attempt",
                "status": "failed",
                "error_summary": error_text,
            }
        )
    return actions


def summarize_unified_action_errors(actions: list[dict[str, Any]]) -> str:
    """Aggregate all unified-action errors into a deterministic retry summary."""
    summary_lines: list[str] = []
    for action in actions:
        error_summary = str(action.get("error_summary") or "").strip()
        if not error_summary:
            continue
        kind = str(action.get("kind") or "action")
        name = str(action.get("action") or "unknown")
        summary_lines.append(f"[{kind}] {name}: {error_summary}")
    if summary_lines:
        return "\n".join(summary_lines)
    return "No explicit action errors recorded, but story outcome was fail."


def format_quality_findings(result: QualityGateResult) -> str:
    """Render static quality findings into a single failure message."""
    lines: list[str] = ["Static quality gates failed."]
    syntax_errors = result.syntax_errors
    doc_violations = result.docstring_violations
    if syntax_errors:
        lines.append("Syntax errors:")
        lines.extend(f"- {item}" for item in syntax_errors)
    if doc_violations:
        lines.append("Docstring violations:")
        lines.extend(f"- {item}" for item in doc_violations)
    return "\n".join(lines)


def command_failure_hints(result: CommandResult) -> list[str]:
    """Derive actionable hints from command failures."""
    if result.exit_code == 0:
        return []
    combined = f"{result.stdout}\n{result.stderr}".lower()
    hints: list[str] = []
    if "no module named" in combined or "command not found" in combined:
        if "ruff" in result.command:
            hints.append("Install ruff (python -m pip install ruff) or disable quality gates.")
        if "mypy" in result.command:
            hints.append("Install mypy (python -m pip install mypy) or adjust mypy config.")
        if "pytest" in result.command:
            hints.append("Install pytest (python -m pip install pytest) or update test scope.")
        if "bandit" in result.command:
            hints.append("Install bandit or set --security-scan-mode if-available.")
    if "permission denied" in combined:
        hints.append("Check filesystem permissions for generated project files.")
    return hints


def dedupe_commands(commands: list[str]) -> list[str]:
    """Remove duplicate commands while preserving order."""
    seen: set[str] = set()
    output: list[str] = []
    for command in commands:
        cleaned = command.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        output.append(cleaned)
    return output
