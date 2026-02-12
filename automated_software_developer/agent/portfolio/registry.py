"""Persistent multi-project portfolio registry with append-only JSONL storage."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path

from automated_software_developer.agent.portfolio.schemas import (
    RegistryEntry,
    new_registry_entry,
    utc_now_iso,
)
from automated_software_developer.agent.security import redact_sensitive_text

REPO_REGISTRY_RELATIVE_PATH = ".autosd_portfolio/registry.jsonl"
AUTOSD_REGISTRY_ENV = "AUTOSD_REGISTRY_PATH"


class PortfolioRegistry:
    """Append-only project portfolio registry with schema validation."""

    def __init__(
        self,
        write_path: Path | None = None,
        read_paths: Iterable[Path] | None = None,
        *,
        cwd: Path | None = None,
    ) -> None:
        """Initialize registry paths and create parent directory for writes."""
        resolved_cwd = cwd or Path.cwd()
        self.write_path = (write_path or self.default_write_path()).expanduser().resolve()
        self.write_path.parent.mkdir(parents=True, exist_ok=True)

        if read_paths is None:
            default_paths = self.default_read_paths(self.write_path, cwd=resolved_cwd)
            self.read_paths = [path.expanduser().resolve() for path in default_paths]
        else:
            self.read_paths = [path.expanduser().resolve() for path in read_paths]

        if self.write_path not in self.read_paths:
            self.read_paths.insert(0, self.write_path)

    @staticmethod
    def default_write_path() -> Path:
        """Resolve default writable registry path from environment or home directory."""
        env_value = os.environ.get(AUTOSD_REGISTRY_ENV)
        if env_value:
            return Path(env_value)
        return Path.home() / ".autosd" / "registry.jsonl"

    @staticmethod
    def default_read_paths(write_path: Path, *, cwd: Path) -> list[Path]:
        """Resolve read paths supporting both home and repository-local registries."""
        paths = [write_path]
        repo_path = (cwd / REPO_REGISTRY_RELATIVE_PATH).resolve()
        if repo_path.exists() and repo_path not in paths:
            paths.append(repo_path)
        return paths

    def register_project(
        self,
        *,
        project_id: str,
        name: str,
        domain: str,
        platforms: list[str],
        repo_url: str | None = None,
        default_branch: str = "main",
        current_version: str = "0.1.0",
        environments: list[str] | None = None,
        telemetry_policy: str = "off",
        data_retention_policy: str = "30d",
        compliance_profile: str = "default",
        template_versions: dict[str, int] | None = None,
        metadata: dict[str, str] | None = None,
    ) -> RegistryEntry:
        """Create and persist a new project entry with safe defaults."""
        existing = self.get(project_id)
        if existing is not None:
            raise ValueError(f"Project '{project_id}' already exists in registry.")
        entry = new_registry_entry(
            project_id=project_id,
            name=name,
            domain=domain,
            platforms=platforms,
            repo_url=repo_url,
            default_branch=default_branch,
            current_version=current_version,
            environments=environments,
            telemetry_policy=telemetry_policy,
            data_retention_policy=data_retention_policy,
            compliance_profile=compliance_profile,
            template_versions=template_versions,
            metadata=metadata,
        )
        self.append(entry)
        return entry

    def append(self, entry: RegistryEntry) -> None:
        """Append one validated registry entry record to JSONL file."""
        payload = _sanitize_json(entry.to_dict())
        with self.write_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True))
            handle.write("\n")

    def list_entries(self, *, include_archived: bool = False) -> list[RegistryEntry]:
        """Return latest registry entries, optionally including archived projects."""
        latest_by_project: dict[str, RegistryEntry] = {}
        for path in self.read_paths:
            if not path.exists() or not path.is_file():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    payload = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if not isinstance(payload, dict):
                    continue
                try:
                    entry = RegistryEntry.from_dict(payload)
                except ValueError:
                    continue
                latest_by_project[entry.project_id] = entry
        entries = sorted(
            latest_by_project.values(),
            key=lambda item: (item.created_at, item.project_id),
        )
        if include_archived:
            return entries
        return [entry for entry in entries if not entry.archived]

    def get(self, project_ref: str) -> RegistryEntry | None:
        """Return latest entry by project id or exact name."""
        lookup = project_ref.strip()
        if not lookup:
            raise ValueError("project_ref must be non-empty.")
        for entry in self.list_entries(include_archived=True):
            if entry.project_id == lookup or entry.name == lookup:
                return entry
        return None

    def update(self, project_ref: str, **changes: object) -> RegistryEntry:
        """Create a new entry version for a project by applying field updates."""
        existing = self.get(project_ref)
        if existing is None:
            raise KeyError(f"Project '{project_ref}' not found.")

        payload = existing.to_dict()
        payload.update(changes)
        payload["project_id"] = existing.project_id
        payload["created_at"] = existing.created_at
        payload["updated_at"] = utc_now_iso()
        entry = RegistryEntry.from_dict(payload)
        self.append(entry)
        return entry

    def retire(self, project_ref: str, *, reason: str) -> RegistryEntry:
        """Archive a project and disable automation by default."""
        existing = self.get(project_ref)
        if existing is None:
            raise KeyError(f"Project '{project_ref}' not found.")
        metadata = dict(existing.metadata)
        metadata["retired_reason"] = reason.strip() or "retired"
        metadata["retired_at"] = utc_now_iso()
        updated = replace(
            existing,
            updated_at=utc_now_iso(),
            archived=True,
            automation_halted=True,
            metadata=metadata,
        )
        self.append(updated)
        return updated

    def status_rows(self, *, include_archived: bool = False) -> list[dict[str, str]]:
        """Return compact status rows for tabular CLI output."""
        rows: list[dict[str, str]] = []
        for entry in self.list_entries(include_archived=include_archived):
            rows.append(
                {
                    "project_id": entry.project_id,
                    "name": entry.name,
                    "version": entry.current_version,
                    "health": entry.health_status,
                    "ci": entry.ci_status,
                    "security": entry.security_scan_status,
                    "archived": "yes" if entry.archived else "no",
                    "halted": "yes" if entry.automation_halted else "no",
                }
            )
        return rows


def _sanitize_json(payload: object) -> object:
    """Recursively sanitize strings before writing to registry logs."""
    if isinstance(payload, str):
        return redact_sensitive_text(payload)
    if isinstance(payload, list):
        return [_sanitize_json(item) for item in payload]
    if isinstance(payload, dict):
        output: dict[str, object] = {}
        for key, item in payload.items():
            output[str(key)] = _sanitize_json(item)
        return output
    return payload
