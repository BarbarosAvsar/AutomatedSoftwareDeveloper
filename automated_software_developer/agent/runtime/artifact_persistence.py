"""Persistence helpers for orchestrator runtime artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from automated_software_developer.agent.architecture import ArchitectureArtifacts
from automated_software_developer.agent.backlog import StoryBacklog
from automated_software_developer.agent.design_doc import build_design_doc_markdown
from automated_software_developer.agent.filesystem import FileWorkspace
from automated_software_developer.agent.models import RefinedRequirements
from automated_software_developer.agent.schemas import (
    validate_backlog_payload,
    validate_sprint_log_event,
)
from automated_software_developer.agent.security import ensure_safe_relative_path


def persist_progress(
    *,
    workspace: FileWorkspace,
    progress_file: str,
    refined_spec_file: str,
    backlog_file: str,
    design_doc_file: str,
    platform_plan_file: str,
    capability_graph_file: str,
    architecture_doc_file: str,
    architecture_components_file: str,
    architecture_adrs_dir: str,
    backlog: StoryBacklog,
    refined: RefinedRequirements,
    platform_adapter_id: str | None = None,
) -> None:
    """Persist progress snapshot for compatibility and observability."""
    output: dict[str, Any] = {
        "project_name": refined.project_name,
        "stack_rationale": refined.stack_rationale,
        "verification_commands": backlog.global_verification_commands,
        "refined_spec": refined_spec_file,
        "backlog": backlog_file,
        "design_doc": design_doc_file,
        "platform_plan": platform_plan_file,
        "capability_graph": capability_graph_file,
        "architecture_doc": architecture_doc_file,
        "architecture_components": architecture_components_file,
        "architecture_adrs": architecture_adrs_dir,
        "platform_adapter_id": platform_adapter_id,
        "stories": [
            {
                "id": item.story_id,
                "title": item.title,
                "status": item.status,
                "attempts": item.attempts,
                "last_error": item.last_error,
            }
            for item in backlog.stories
        ],
        # Legacy compatibility with prior progress schema.
        "tasks": [
            {
                "id": item.story_id,
                "title": item.title,
                "status": item.status,
                "attempts": item.attempts,
                "last_error": item.last_error,
                "results": [],
            }
            for item in backlog.stories
        ],
    }
    workspace.write_file(progress_file, json.dumps(output, indent=2))


def persist_backlog(
    *,
    workspace: FileWorkspace,
    backlog_file: str,
    backlog: StoryBacklog,
) -> None:
    """Persist the latest backlog JSON artifact."""
    payload = backlog.to_dict()
    validate_backlog_payload(payload)
    workspace.write_file(backlog_file, json.dumps(payload, indent=2))


def persist_design_doc(
    *,
    workspace: FileWorkspace,
    design_doc_file: str,
    refined: RefinedRequirements,
    backlog: StoryBacklog,
    phase: str,
) -> None:
    """Persist or update internal design doc artifact."""
    content = build_design_doc_markdown(refined=refined, backlog=backlog, phase=phase)
    workspace.write_file(design_doc_file, content)


def append_sprint_log(
    *,
    workspace: FileWorkspace,
    sprint_log_file: str,
    payload: dict[str, Any],
) -> None:
    """Append a sprint event to jsonl log."""
    validate_sprint_log_event(payload)
    path = ensure_safe_relative_path(workspace.base_dir, sprint_log_file)
    root = workspace.base_dir.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True))
        handle.write("\n")
    workspace.changed_files.add(str(path.relative_to(root)).replace("\\", "/"))


def track_architecture_artifacts(
    *,
    workspace: FileWorkspace,
    artifacts: ArchitectureArtifacts,
) -> None:
    """Track architecture artifacts in workspace change list."""
    root = workspace.base_dir.resolve()
    paths = [artifacts.architecture_doc, artifacts.components_json, *artifacts.adr_files]
    for path in paths:
        resolved = Path(path).resolve()
        workspace.changed_files.add(str(resolved.relative_to(root)).replace("\\", "/"))
