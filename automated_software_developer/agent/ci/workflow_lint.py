"""Static workflow linting for GitHub Actions."""

from __future__ import annotations

import re
from collections.abc import Hashable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class DuplicateKeyError(ValueError):
    """Raised when duplicate keys are found in workflow YAML."""

    def __init__(self, key: str) -> None:
        super().__init__(f"duplicate key: {key}")
        self.key = key


class UniqueKeyLoader(yaml.SafeLoader):
    """YAML loader that rejects duplicate keys."""

    def construct_mapping(self, node: Any, deep: bool = False) -> dict[Hashable, Any]:
        mapping: dict[Hashable, Any] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)  # type: ignore[no-untyped-call]
            if key in mapping:
                raise DuplicateKeyError(str(key))
            mapping[key] = self.construct_object(  # type: ignore[no-untyped-call]
                value_node,
                deep=deep,
            )
        return mapping


@dataclass(frozen=True)
class WorkflowLintResult:
    """Workflow lint result with errors."""

    path: Path
    errors: tuple[str, ...]

    @property
    def passed(self) -> bool:
        """Return True when no lint errors are present."""
        return not self.errors


def lint_workflows(root: Path) -> list[WorkflowLintResult]:
    """Lint all workflows under .github/workflows."""
    workflow_dir = root / ".github" / "workflows"
    if not workflow_dir.exists():
        return [WorkflowLintResult(path=workflow_dir, errors=("missing_workflows",))]
    results: list[WorkflowLintResult] = []
    for workflow in sorted(workflow_dir.glob("*.yml")):
        errors = tuple(validate_workflow(workflow))
        results.append(WorkflowLintResult(path=workflow, errors=errors))
    return results


def validate_workflow(path: Path) -> list[str]:
    """Validate workflow YAML and enforce CI safety rules."""
    try:
        data = yaml.load(
            path.read_text(encoding="utf-8"),
            Loader=UniqueKeyLoader,  # noqa: S506
        )
    except DuplicateKeyError as exc:
        return [f"duplicate_key:{exc.key}"]
    except yaml.YAMLError as exc:
        return [f"invalid_yaml:{exc}"]
    if not isinstance(data, dict):
        return ["workflow_root_not_mapping"]
    on_key = "on" if "on" in data else True if True in data else None
    if on_key is None:
        return ["missing_on"]
    if "jobs" not in data or not isinstance(data["jobs"], dict):
        return ["missing_jobs"]
    errors: list[str] = []
    errors.extend(_validate_permissions(data))
    errors.extend(_validate_jobs(data["jobs"]))
    return errors


def _validate_permissions(data: dict[str, Any]) -> list[str]:
    permissions = data.get("permissions")
    if permissions is None:
        return ["missing_permissions"]
    if isinstance(permissions, str):
        if permissions in {"read-all", "write-all"}:
            return [f"permissions_too_broad:{permissions}"]
        return ["permissions_not_mapping"]
    if not isinstance(permissions, dict):
        return ["permissions_not_mapping"]
    contents = permissions.get("contents")
    if contents != "read":
        return ["permissions_contents_not_read"]
    for key, value in permissions.items():
        if value not in {"read", "write", "none"}:
            return [f"permissions_invalid_value:{key}"]
    return []


def _validate_jobs(jobs: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for job_id, job in jobs.items():
        if not isinstance(job, dict):
            errors.append(f"job_not_mapping:{job_id}")
            continue
        if "runs-on" not in job:
            errors.append(f"missing_runs_on:{job_id}")
        steps = job.get("steps", [])
        if not isinstance(steps, list):
            errors.append(f"steps_not_list:{job_id}")
            continue
        for step in steps:
            errors.extend(_validate_step(step, job_id))
    return errors


def _validate_step(step: Any, job_id: str) -> list[str]:
    if not isinstance(step, dict):
        return [f"step_not_mapping:{job_id}"]
    errors: list[str] = []
    uses = step.get("uses")
    if isinstance(uses, str) and not _is_pinned_action(uses):
        errors.append(f"unpin_action:{uses}")
    run = step.get("run")
    if isinstance(run, str):
        errors.extend(_validate_run_command(run))
    for value in step.values():
        if isinstance(value, str) and not _expressions_balanced(value):
            errors.append("invalid_expression_syntax")
            break
    return errors


def _validate_run_command(run: str) -> list[str]:
    errors: list[str] = []
    if re.search(r"^\s*set\s+-x\b", run, flags=re.MULTILINE):
        errors.append("unsafe_set_x")
    if re.search(r"^\s*set\s+-o\s+xtrace\b", run, flags=re.MULTILINE):
        errors.append("unsafe_set_xtrace")
    if re.search(r"^\s*printenv\b", run, flags=re.MULTILINE):
        errors.append("unsafe_printenv")
    if re.search(r"^\s*env\b", run, flags=re.MULTILINE):
        errors.append("unsafe_env_dump")
    if re.search(r"echo\s+.*\${{\s*secrets\.", run):
        errors.append("unsafe_echo_secrets")
    return errors


def _is_pinned_action(uses: str) -> bool:
    """Return True if action reference is pinned to a SHA or local action."""
    if uses.startswith("./") or uses.startswith("docker://"):
        return True
    if "@" not in uses:
        return False
    _, ref = uses.rsplit("@", 1)
    return bool(_is_sha(ref))


def _is_sha(ref: str) -> bool:
    """Check if the reference looks like a 40-char SHA."""
    if len(ref) != 40:
        return False
    return all(char in "0123456789abcdef" for char in ref.lower())


def _expressions_balanced(text: str) -> bool:
    """Ensure GitHub expression delimiters are balanced."""
    return text.count("${{") == text.count("}}")
