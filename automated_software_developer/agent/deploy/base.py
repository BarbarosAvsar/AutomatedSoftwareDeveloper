"""Deployment target abstractions and orchestrator."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from automated_software_developer.agent.portfolio.registry import PortfolioRegistry
from automated_software_developer.agent.portfolio.schemas import RegistryEntry
from automated_software_developer.logging_utils import get_logger

LOGGER = get_logger()


@dataclass(frozen=True)
class DeploymentResult:
    """Result of deploy/promotion/rollback operation."""

    project_id: str
    environment: str
    target: str
    success: bool
    version: str
    message: str
    deployed_at: str
    strategy: str
    scaffold_only: bool


class DeploymentTarget(ABC):
    """Abstract deployment target plugin."""

    target_id: str
    supports_canary: bool = False

    @abstractmethod
    def deploy(
        self,
        *,
        project_dir: Path,
        environment: str,
        version: str,
        strategy: str,
        execute: bool,
    ) -> DeploymentResult:
        """Deploy project to the target."""

    @abstractmethod
    def rollback(
        self,
        *,
        project_dir: Path,
        environment: str,
        version: str,
        execute: bool,
    ) -> DeploymentResult:
        """Rollback project deployment on target."""

    def promote(
        self,
        *,
        project_dir: Path,
        source_environment: str,
        target_environment: str,
        version: str,
        execute: bool,
    ) -> DeploymentResult:
        """Promote version from one environment to another."""
        del source_environment
        return self.deploy(
            project_dir=project_dir,
            environment=target_environment,
            version=version,
            strategy="standard",
            execute=execute,
        )


class DeploymentOrchestrator:
    """Coordinates deployment target selection and portfolio state updates."""

    def __init__(
        self,
        *,
        registry: PortfolioRegistry,
        targets: dict[str, DeploymentTarget],
    ) -> None:
        """Initialize deployment orchestrator with registry and target plugins."""
        self.registry = registry
        self.targets = targets

    def deploy(
        self,
        *,
        project_ref: str,
        environment: str,
        target: str,
        strategy: str,
        execute: bool,
    ) -> DeploymentResult:
        """Deploy one project to selected target/environment."""
        LOGGER.info(
            "Deploy requested",
            extra={
                "project_ref": project_ref,
                "environment": environment,
                "target": target,
                "strategy": strategy,
                "execute": execute,
            },
        )
        entry = _require_project(self.registry, project_ref)
        deployment_target = _require_target(self.targets, target)
        resolved_strategy = _normalize_strategy(strategy, deployment_target.supports_canary)
        project_dir = _resolve_project_dir(entry)
        result = deployment_target.deploy(
            project_dir=project_dir,
            environment=environment,
            version=entry.current_version,
            strategy=resolved_strategy,
            execute=execute,
        )
        result = _with_project_id(result, entry.project_id)
        if result.success:
            environments = list(entry.environments)
            if environment not in environments:
                environments.append(environment)
            self.registry.update(
                entry.project_id,
                environments=environments,
                health_status="healthy",
                last_deploy={
                    "environment": environment,
                    "target": target,
                    "version": result.version,
                    "timestamp": result.deployed_at,
                },
                metadata={
                    **entry.metadata,
                    "last_deploy_strategy": resolved_strategy,
                },
            )
            LOGGER.info(
                "Deploy succeeded",
                extra={
                    "project_id": entry.project_id,
                    "environment": environment,
                    "target": target,
                },
            )
        else:
            LOGGER.warning(
                "Deploy failed",
                extra={
                    "project_id": entry.project_id,
                    "environment": environment,
                    "target": target,
                },
            )
        return result

    def rollback(
        self,
        *,
        project_ref: str,
        environment: str,
        target: str,
        execute: bool,
    ) -> DeploymentResult:
        """Rollback one project deployment on a target."""
        LOGGER.info(
            "Rollback requested",
            extra={
                "project_ref": project_ref,
                "environment": environment,
                "target": target,
                "execute": execute,
            },
        )
        entry = _require_project(self.registry, project_ref)
        deployment_target = _require_target(self.targets, target)
        project_dir = _resolve_project_dir(entry)
        result = deployment_target.rollback(
            project_dir=project_dir,
            environment=environment,
            version=entry.current_version,
            execute=execute,
        )
        result = _with_project_id(result, entry.project_id)
        if result.success:
            self.registry.update(
                entry.project_id,
                health_status="degraded",
                metadata={
                    **entry.metadata,
                    "last_rollback_at": result.deployed_at,
                },
            )
            LOGGER.info(
                "Rollback succeeded",
                extra={
                    "project_id": entry.project_id,
                    "environment": environment,
                    "target": target,
                },
            )
        else:
            LOGGER.warning(
                "Rollback failed",
                extra={
                    "project_id": entry.project_id,
                    "environment": environment,
                    "target": target,
                },
            )
        return result

    def promote(
        self,
        *,
        project_ref: str,
        source_environment: str,
        target_environment: str,
        target: str,
        execute: bool,
    ) -> DeploymentResult:
        """Promote a deployed version from one environment to another."""
        LOGGER.info(
            "Promotion requested",
            extra={
                "project_ref": project_ref,
                "source_environment": source_environment,
                "target_environment": target_environment,
                "target": target,
                "execute": execute,
            },
        )
        entry = _require_project(self.registry, project_ref)
        deployment_target = _require_target(self.targets, target)
        project_dir = _resolve_project_dir(entry)
        result = deployment_target.promote(
            project_dir=project_dir,
            source_environment=source_environment,
            target_environment=target_environment,
            version=entry.current_version,
            execute=execute,
        )
        result = _with_project_id(result, entry.project_id)
        if result.success:
            environments = list(entry.environments)
            if target_environment not in environments:
                environments.append(target_environment)
            self.registry.update(
                entry.project_id,
                environments=environments,
                health_status="healthy",
                last_deploy={
                    "environment": target_environment,
                    "target": target,
                    "version": result.version,
                    "timestamp": result.deployed_at,
                },
            )
            LOGGER.info(
                "Promotion succeeded",
                extra={
                    "project_id": entry.project_id,
                    "target_environment": target_environment,
                    "target": target,
                },
            )
        else:
            LOGGER.warning(
                "Promotion failed",
                extra={
                    "project_id": entry.project_id,
                    "target_environment": target_environment,
                    "target": target,
                },
            )
        return result


def utc_now() -> str:
    """Return current UTC timestamp for deployment events."""
    return datetime.now(tz=UTC).isoformat()


def _require_project(registry: PortfolioRegistry, project_ref: str) -> RegistryEntry:
    """Resolve project entry or raise if missing."""
    entry = registry.get(project_ref)
    if entry is None:
        raise KeyError(f"Project '{project_ref}' not found.")
    return entry


def _require_target(
    targets: dict[str, DeploymentTarget],
    target_id: str,
) -> DeploymentTarget:
    """Resolve target plugin or raise for unsupported target id."""
    target = targets.get(target_id)
    if target is None:
        allowed = ", ".join(sorted(targets))
        raise ValueError(f"Unknown deployment target '{target_id}'. Allowed: {allowed}")
    return target


def _normalize_strategy(strategy: str, supports_canary: bool) -> str:
    """Normalize deployment strategy according to target capabilities."""
    normalized = strategy.strip().lower() or "standard"
    if normalized in {"canary", "blue-green"} and not supports_canary:
        return "standard"
    return normalized


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
        f"Project '{entry.project_id}' has no local path configured in metadata "
        "(local_path/workspace_path/project_path)."
    )


def _with_project_id(result: DeploymentResult, project_id: str) -> DeploymentResult:
    """Return deployment result with normalized project identifier."""
    return DeploymentResult(
        project_id=project_id,
        environment=result.environment,
        target=result.target,
        success=result.success,
        version=result.version,
        message=result.message,
        deployed_at=result.deployed_at,
        strategy=result.strategy,
        scaffold_only=result.scaffold_only,
    )
