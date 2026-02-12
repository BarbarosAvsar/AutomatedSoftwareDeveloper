"""Schema-first models and validation for portfolio registry entries."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

REGISTRY_ENTRY_SCHEMA: dict[str, Any] = {
    "title": "PortfolioRegistryEntry",
    "type": "object",
    "required": [
        "project_id",
        "name",
        "created_at",
        "updated_at",
        "domain",
        "platforms",
        "default_branch",
        "current_version",
        "version_history",
        "environments",
        "health_status",
        "telemetry_policy",
        "data_retention_policy",
        "compliance_profile",
        "template_versions",
        "ci_status",
        "security_scan_status",
        "automation_halted",
        "archived",
        "pending_push",
        "metadata",
    ],
    "properties": {
        "project_id": {"type": "string", "minLength": 1},
        "name": {"type": "string", "minLength": 1},
        "created_at": {"type": "string", "format": "date-time"},
        "updated_at": {"type": "string", "format": "date-time"},
        "domain": {"type": "string", "minLength": 1},
        "platforms": {"type": "array", "items": {"type": "string"}},
        "repo_url": {"type": ["string", "null"]},
        "default_branch": {"type": "string", "minLength": 1},
        "current_version": {"type": "string", "minLength": 1},
        "version_history": {"type": "array", "items": {"type": "string"}},
        "last_deploy": {
            "type": ["object", "null"],
            "required": ["environment", "target", "version", "timestamp"],
            "properties": {
                "environment": {"type": "string"},
                "target": {"type": "string"},
                "version": {"type": "string"},
                "timestamp": {"type": "string", "format": "date-time"},
            },
        },
        "environments": {"type": "array", "items": {"type": "string"}},
        "health_status": {"type": "string"},
        "telemetry_policy": {"type": "string"},
        "data_retention_policy": {"type": "string"},
        "compliance_profile": {"type": "string"},
        "template_versions": {"type": "object", "additionalProperties": {"type": "integer"}},
        "ci_status": {"type": "string"},
        "security_scan_status": {"type": "string"},
        "automation_halted": {"type": "boolean"},
        "archived": {"type": "boolean"},
        "pending_push": {"type": "boolean"},
        "metadata": {"type": "object", "additionalProperties": {"type": "string"}},
    },
}


def utc_now_iso() -> str:
    """Return current UTC timestamp in ISO-8601 format."""
    return datetime.now(tz=UTC).isoformat()


def _require_string(value: Any, field_name: str) -> str:
    """Validate a non-empty string field."""
    if not isinstance(value, str):
        raise ValueError(f"Expected '{field_name}' to be a string.")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"Expected '{field_name}' to be non-empty.")
    return cleaned


def _require_string_list(value: Any, field_name: str) -> list[str]:
    """Validate a list of non-empty strings."""
    if not isinstance(value, list):
        raise ValueError(f"Expected '{field_name}' to be a list.")
    output: list[str] = []
    for index, item in enumerate(value):
        output.append(_require_string(item, f"{field_name}[{index}]"))
    return output


def _require_bool(value: Any, field_name: str) -> bool:
    """Validate a boolean field."""
    if not isinstance(value, bool):
        raise ValueError(f"Expected '{field_name}' to be a boolean.")
    return value


def _require_optional_string(value: Any, field_name: str) -> str | None:
    """Validate an optional string field."""
    if value is None:
        return None
    return _require_string(value, field_name)


def _require_dict_string_int(value: Any, field_name: str) -> dict[str, int]:
    """Validate object values as integer map."""
    if not isinstance(value, Mapping):
        raise ValueError(f"Expected '{field_name}' to be an object.")
    output: dict[str, int] = {}
    for key, item in value.items():
        normalized_key = _require_string(key, f"{field_name} key")
        if not isinstance(item, int):
            raise ValueError(f"Expected '{field_name}[{normalized_key}]' to be an integer.")
        output[normalized_key] = item
    return output


def _require_dict_string_string(value: Any, field_name: str) -> dict[str, str]:
    """Validate object values as string map."""
    if not isinstance(value, Mapping):
        raise ValueError(f"Expected '{field_name}' to be an object.")
    output: dict[str, str] = {}
    for key, item in value.items():
        normalized_key = _require_string(key, f"{field_name} key")
        output[normalized_key] = _require_string(item, f"{field_name}[{normalized_key}]")
    return output


def _validate_iso_timestamp(value: str, field_name: str) -> str:
    """Validate field as ISO timestamp."""
    try:
        datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Expected '{field_name}' to be ISO timestamp.") from exc
    return value


@dataclass(frozen=True)
class DeployRecord:
    """Latest deploy metadata persisted in project registry."""

    environment: str
    target: str
    version: str
    timestamp: str

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> DeployRecord:
        """Build deploy record from untrusted mapping."""
        return cls(
            environment=_require_string(payload.get("environment"), "last_deploy.environment"),
            target=_require_string(payload.get("target"), "last_deploy.target"),
            version=_require_string(payload.get("version"), "last_deploy.version"),
            timestamp=_validate_iso_timestamp(
                _require_string(payload.get("timestamp"), "last_deploy.timestamp"),
                "last_deploy.timestamp",
            ),
        )

    def to_dict(self) -> dict[str, str]:
        """Serialize deploy record as JSON object."""
        return {
            "environment": self.environment,
            "target": self.target,
            "version": self.version,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class RegistryEntry:
    """Canonical project entry in persistent portfolio registry."""

    project_id: str
    name: str
    created_at: str
    updated_at: str
    domain: str
    platforms: list[str]
    repo_url: str | None
    default_branch: str
    current_version: str
    version_history: list[str]
    last_deploy: DeployRecord | None
    environments: list[str]
    health_status: str
    telemetry_policy: str
    data_retention_policy: str
    compliance_profile: str
    template_versions: dict[str, int]
    ci_status: str
    security_scan_status: str
    automation_halted: bool
    archived: bool
    pending_push: bool
    metadata: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> RegistryEntry:
        """Validate and build registry entry from raw payload."""
        last_deploy_raw = payload.get("last_deploy")
        if last_deploy_raw is None:
            last_deploy = None
        elif isinstance(last_deploy_raw, Mapping):
            last_deploy = DeployRecord.from_dict(last_deploy_raw)
        else:
            raise ValueError("Expected 'last_deploy' to be object or null.")

        return cls(
            project_id=_require_string(payload.get("project_id"), "project_id"),
            name=_require_string(payload.get("name"), "name"),
            created_at=_validate_iso_timestamp(
                _require_string(payload.get("created_at"), "created_at"),
                "created_at",
            ),
            updated_at=_validate_iso_timestamp(
                _require_string(payload.get("updated_at"), "updated_at"),
                "updated_at",
            ),
            domain=_require_string(payload.get("domain"), "domain"),
            platforms=_require_string_list(payload.get("platforms"), "platforms"),
            repo_url=_require_optional_string(payload.get("repo_url"), "repo_url"),
            default_branch=_require_string(payload.get("default_branch"), "default_branch"),
            current_version=_require_string(payload.get("current_version"), "current_version"),
            version_history=_require_string_list(payload.get("version_history"), "version_history"),
            last_deploy=last_deploy,
            environments=_require_string_list(payload.get("environments"), "environments"),
            health_status=_require_string(payload.get("health_status"), "health_status"),
            telemetry_policy=_require_string(payload.get("telemetry_policy"), "telemetry_policy"),
            data_retention_policy=_require_string(
                payload.get("data_retention_policy"),
                "data_retention_policy",
            ),
            compliance_profile=_require_string(
                payload.get("compliance_profile"),
                "compliance_profile",
            ),
            template_versions=_require_dict_string_int(
                payload.get("template_versions"),
                "template_versions",
            ),
            ci_status=_require_string(payload.get("ci_status"), "ci_status"),
            security_scan_status=_require_string(
                payload.get("security_scan_status"),
                "security_scan_status",
            ),
            automation_halted=_require_bool(payload.get("automation_halted"), "automation_halted"),
            archived=_require_bool(payload.get("archived"), "archived"),
            pending_push=_require_bool(payload.get("pending_push"), "pending_push"),
            metadata=_require_dict_string_string(payload.get("metadata", {}), "metadata"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize registry entry as JSON-encodable object."""
        return {
            "project_id": self.project_id,
            "name": self.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "domain": self.domain,
            "platforms": self.platforms,
            "repo_url": self.repo_url,
            "default_branch": self.default_branch,
            "current_version": self.current_version,
            "version_history": self.version_history,
            "last_deploy": self.last_deploy.to_dict() if self.last_deploy else None,
            "environments": self.environments,
            "health_status": self.health_status,
            "telemetry_policy": self.telemetry_policy,
            "data_retention_policy": self.data_retention_policy,
            "compliance_profile": self.compliance_profile,
            "template_versions": self.template_versions,
            "ci_status": self.ci_status,
            "security_scan_status": self.security_scan_status,
            "automation_halted": self.automation_halted,
            "archived": self.archived,
            "pending_push": self.pending_push,
            "metadata": self.metadata,
        }


def new_registry_entry(
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
    """Create a new registry entry with safe defaults."""
    timestamp = utc_now_iso()
    resolved_platforms = [_require_string(item, "platforms item") for item in platforms]
    if not resolved_platforms:
        raise ValueError("platforms must include at least one value.")
    resolved_environments = environments or ["dev"]
    resolved_templates = template_versions or {}
    resolved_metadata = _require_dict_string_string(metadata or {}, "metadata")
    return RegistryEntry(
        project_id=_require_string(project_id, "project_id"),
        name=_require_string(name, "name"),
        created_at=timestamp,
        updated_at=timestamp,
        domain=_require_string(domain, "domain"),
        platforms=resolved_platforms,
        repo_url=repo_url,
        default_branch=_require_string(default_branch, "default_branch"),
        current_version=_require_string(current_version, "current_version"),
        version_history=[_require_string(current_version, "current_version")],
        last_deploy=None,
        environments=resolved_environments,
        health_status="unknown",
        telemetry_policy=telemetry_policy,
        data_retention_policy=data_retention_policy,
        compliance_profile=compliance_profile,
        template_versions=resolved_templates,
        ci_status="unknown",
        security_scan_status="unknown",
        automation_halted=False,
        archived=False,
        pending_push=False,
        metadata=resolved_metadata,
    )
