"""Multi-project patch orchestration with bounded local GitOps workflow."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from automated_software_developer.agent.executor import CommandExecutor
from automated_software_developer.agent.gitops import GitOperationResult, GitOpsManager
from automated_software_developer.agent.portfolio.registry import PortfolioRegistry
from automated_software_developer.agent.portfolio.schemas import RegistryEntry
from automated_software_developer.agent.quality import (
    build_quality_gate_plan,
    evaluate_python_quality,
)

SEMVER_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


@dataclass(frozen=True)
class PatchFilters:
    """Optional filter set for selecting projects for batch patching."""

    domain: str | None = None
    platform: str | None = None
    needs_security: bool = False
    needs_upgrade: bool = False
    telemetry_enabled: bool = False
    deployed: bool = False


@dataclass(frozen=True)
class PatchOutcome:
    """Outcome metadata for one patched project."""

    project_id: str
    branch: str | None
    success: bool
    old_version: str
    new_version: str | None
    bump_kind: str
    commit_sha: str | None
    pending_push: bool
    error: str | None


class PatchEngine:
    """Coordinates patch branch creation, gates, commit, and registry updates."""

    def __init__(
        self,
        registry: PortfolioRegistry,
        gitops: GitOpsManager | None = None,
        executor: CommandExecutor | None = None,
    ) -> None:
        """Initialize patch engine with registry and GitOps helper."""
        self.registry = registry
        self.gitops = gitops or GitOpsManager()
        self.executor = executor or CommandExecutor(timeout_seconds=300)

    def patch_project(
        self,
        project_ref: str,
        *,
        reason: str,
        auto_push: bool,
        create_tag: bool,
    ) -> PatchOutcome:
        """Apply a patch workflow to one project by id or name."""
        entry = self.registry.get(project_ref)
        if entry is None:
            raise KeyError(f"Project '{project_ref}' not found.")
        return self._patch_entry(entry, reason=reason, auto_push=auto_push, create_tag=create_tag)

    def patch_all(
        self,
        *,
        reason: str,
        filters: PatchFilters,
        auto_push: bool,
        create_tag: bool,
    ) -> list[PatchOutcome]:
        """Apply patch workflow to all projects matching filters."""
        outcomes: list[PatchOutcome] = []
        for entry in self.registry.list_entries(include_archived=False):
            if not _matches_filters(entry, filters):
                continue
            outcomes.append(
                self._patch_entry(
                    entry,
                    reason=reason,
                    auto_push=auto_push,
                    create_tag=create_tag,
                )
            )
        return outcomes

    def _patch_entry(
        self,
        entry: RegistryEntry,
        *,
        reason: str,
        auto_push: bool,
        create_tag: bool,
    ) -> PatchOutcome:
        """Run patch workflow for one concrete registry entry."""
        if entry.archived or entry.automation_halted:
            return PatchOutcome(
                project_id=entry.project_id,
                branch=None,
                success=False,
                old_version=entry.current_version,
                new_version=None,
                bump_kind="patch",
                commit_sha=None,
                pending_push=False,
                error="Project is archived or halted.",
            )

        project_dir = _resolve_project_dir(entry)
        timestamp = datetime.now(tz=UTC).strftime("%Y%m%d%H%M%S%f")
        branch = f"autosd/patch-{entry.project_id}-{timestamp}"
        bump_kind = classify_change_reason(reason)
        new_version = bump_semver(entry.current_version, bump_kind)

        try:
            self.gitops.ensure_repository(project_dir)
            self.gitops.checkout_new_branch(project_dir, branch)
            self._apply_patch_files(
                project_dir=project_dir,
                entry=entry,
                reason=reason,
                old_version=entry.current_version,
                new_version=new_version,
                bump_kind=bump_kind,
            )
            self._run_project_gates(project_dir)
            tag = f"v{new_version}" if create_tag else None
            message = (
                f"chore(patch): {reason.strip() or 'maintenance update'} "
                f"[{bump_kind}] {entry.current_version} -> {new_version}"
            )
            git_result = self.gitops.commit_push_tag(
                repo_dir=project_dir,
                message=message,
                branch=branch,
                auto_push=auto_push,
                tag=tag,
            )
            self._record_patch_success(
                entry,
                new_version=new_version,
                git_result=git_result,
                reason=reason,
                bump_kind=bump_kind,
            )
            return PatchOutcome(
                project_id=entry.project_id,
                branch=branch,
                success=True,
                old_version=entry.current_version,
                new_version=new_version,
                bump_kind=bump_kind,
                commit_sha=git_result.commit_sha,
                pending_push=git_result.pending_push,
                error=None,
            )
        except Exception as exc:  # noqa: BLE001
            self.registry.update(
                entry.project_id,
                ci_status="red",
                metadata={
                    **entry.metadata,
                    "last_patch_error": str(exc),
                },
            )
            return PatchOutcome(
                project_id=entry.project_id,
                branch=branch,
                success=False,
                old_version=entry.current_version,
                new_version=None,
                bump_kind=bump_kind,
                commit_sha=None,
                pending_push=False,
                error=str(exc),
            )

    def _apply_patch_files(
        self,
        *,
        project_dir: Path,
        entry: RegistryEntry,
        reason: str,
        old_version: str,
        new_version: str,
        bump_kind: str,
    ) -> None:
        """Write deterministic changelog and version updates for patch branch."""
        readme = project_dir / "README.md"
        if not readme.exists():
            readme.write_text(f"# {entry.name}\n\nGenerated project.\n", encoding="utf-8")

        changelog_dir = project_dir / ".autosd" / "changelogs"
        changelog_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        changelog_file = changelog_dir / f"{stamp.replace(':', '')}_{entry.project_id}.md"
        changelog_file.write_text(
            "\n".join(
                [
                    f"# Patch {stamp}",
                    "",
                    f"Project: {entry.project_id}",
                    f"Reason: {reason.strip() or 'maintenance update'}",
                    f"Change Type: {bump_kind}",
                    f"Version: {old_version} -> {new_version}",
                    "",
                    "## Notes",
                    "- Applied automated patch workflow.",
                    "- Executed quality gates before commit.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        pyproject = project_dir / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text(encoding="utf-8")
            updated_content = re.sub(
                r'(version\s*=\s*")([0-9]+\.[0-9]+\.[0-9]+)(")',
                rf"\\g<1>{new_version}\\g<3>",
                content,
                count=1,
            )
            if updated_content != content:
                pyproject.write_text(updated_content, encoding="utf-8")

    def _run_project_gates(self, project_dir: Path) -> None:
        """Run quality gates and static checks for patched project."""
        plan = build_quality_gate_plan(
            project_dir,
            enforce_quality_gates=True,
            enable_security_scan=False,
            security_scan_mode="off",
        )
        commands = [*plan.format_commands, *plan.verification_commands]
        results = self.executor.run_many(commands, cwd=project_dir)
        if results and results[-1].exit_code != 0:
            failed = results[-1]
            raise RuntimeError(
                f"Quality gate failed: {failed.command}\n"
                f"stdout: {failed.stdout.strip()}\n"
                f"stderr: {failed.stderr.strip()}"
            )
        static_quality = evaluate_python_quality(project_dir, enforce_docstrings=False)
        if not static_quality.passed:
            findings = static_quality.syntax_errors + static_quality.docstring_violations
            raise RuntimeError("Static quality checks failed: " + "; ".join(findings))

    def _record_patch_success(
        self,
        entry: RegistryEntry,
        *,
        new_version: str,
        git_result: GitOperationResult,
        reason: str,
        bump_kind: str,
    ) -> None:
        """Persist successful patch metadata back to registry."""
        metadata = {
            **entry.metadata,
            "last_patch_reason": reason.strip() or "maintenance update",
            "last_patch_kind": bump_kind,
        }
        version_history = list(entry.version_history)
        if not version_history or version_history[-1] != new_version:
            version_history.append(new_version)
        self.registry.update(
            entry.project_id,
            current_version=new_version,
            version_history=version_history,
            ci_status="green",
            pending_push=git_result.pending_push,
            metadata=metadata,
        )


def classify_change_reason(reason: str) -> str:
    """Classify patch level from reason text using deterministic heuristics."""
    lowered = reason.lower()
    if any(token in lowered for token in ("breaking", "migration", "major")):
        return "major"
    if any(token in lowered for token in ("feature", "enhancement", "minor")):
        return "minor"
    return "patch"


def bump_semver(version: str, bump_kind: str) -> str:
    """Bump semantic version according to patch classification."""
    match = SEMVER_PATTERN.match(version.strip())
    if match is None:
        return "0.1.0"
    major, minor, patch = (int(part) for part in match.groups())
    if bump_kind == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump_kind == "minor":
        minor += 1
        patch = 0
    else:
        patch += 1
    return f"{major}.{minor}.{patch}"


def _resolve_project_dir(entry: RegistryEntry) -> Path:
    """Resolve local project path from registry metadata."""
    for key in ("local_path", "workspace_path", "project_path"):
        value = entry.metadata.get(key)
        if value is None:
            continue
        candidate = Path(value).expanduser().resolve()
        if candidate.exists() and candidate.is_dir():
            return candidate
    raise RuntimeError(
        f"Project '{entry.project_id}' has no valid local path in metadata "
        "(expected one of: local_path, workspace_path, project_path)."
    )


def _matches_filters(entry: RegistryEntry, filters: PatchFilters) -> bool:
    """Return whether registry entry satisfies batch filter selection."""
    if filters.domain is not None and entry.domain != filters.domain:
        return False
    if filters.platform is not None and filters.platform not in entry.platforms:
        return False
    if filters.needs_security and entry.security_scan_status == "green":
        return False
    if filters.needs_upgrade and entry.metadata.get("needs_upgrade", "false") != "true":
        return False
    if filters.telemetry_enabled and entry.telemetry_policy == "off":
        return False
    return not (filters.deployed and entry.last_deploy is None)
