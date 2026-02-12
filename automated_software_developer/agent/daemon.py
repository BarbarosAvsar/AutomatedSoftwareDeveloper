"""Non-interactive daemon mode for company workflow execution."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from automated_software_developer.agent.audit import AuditLogger
from automated_software_developer.agent.departments.base import AgentContext, WorkOrder
from automated_software_developer.agent.departments.engineering import EngineeringAgent
from automated_software_developer.agent.departments.operations import (
    OperationsAgent,
    ReleaseManager,
)
from automated_software_developer.agent.departments.security import SecurityAgent
from automated_software_developer.agent.deploy import (
    DeploymentOrchestrator,
    default_deployment_targets,
)
from automated_software_developer.agent.incidents.engine import IncidentEngine
from automated_software_developer.agent.orchestrator import SoftwareDevelopmentAgent
from automated_software_developer.agent.patching import PatchEngine
from automated_software_developer.agent.policy.engine import (
    EffectivePolicy,
    resolve_effective_policy,
)
from automated_software_developer.agent.portfolio.registry import PortfolioRegistry
from automated_software_developer.agent.providers.base import LLMProvider
from automated_software_developer.agent.providers.mock_provider import MockProvider


@dataclass(frozen=True)
class DaemonConfig:
    """Configuration for daemon run loop."""

    requirements_dir: Path
    projects_dir: Path
    registry_path: Path
    incidents_path: Path
    incident_signals_path: Path | None = None
    environment: str = "staging"
    deploy_target: str = "generic_container"
    execute_deploy: bool = False


class CompanyDaemon:
    """Runs the end-to-end company workflow without interaction."""

    def __init__(
        self,
        *,
        provider: LLMProvider,
        config: DaemonConfig,
        audit_logger: AuditLogger | None = None,
    ) -> None:
        """Initialize daemon with provider and configuration."""
        self.provider = provider
        self.config = config
        self.registry = PortfolioRegistry(
            write_path=config.registry_path,
            read_paths=[config.registry_path],
        )
        self.audit_logger = audit_logger or AuditLogger()
        self.security_agent = SecurityAgent()
        self.release_manager = ReleaseManager()
        self.operations_agent = OperationsAgent(audit_logger=self.audit_logger)
        patch_engine = PatchEngine(registry=self.registry)
        deployment_orchestrator = DeploymentOrchestrator(
            registry=self.registry,
            targets=default_deployment_targets(),
        )
        self.incident_engine = IncidentEngine(
            registry=self.registry,
            patch_engine=patch_engine,
            deployment_orchestrator=deployment_orchestrator,
            incidents_path=config.incidents_path,
        )

    def run_once(self) -> list[str]:
        """Run one daemon cycle and return processed project IDs."""
        processed: list[str] = []
        self.config.requirements_dir.mkdir(parents=True, exist_ok=True)
        self.config.projects_dir.mkdir(parents=True, exist_ok=True)
        for requirements_file in sorted(self.config.requirements_dir.glob("*.md")):
            project_id = requirements_file.stem
            requirements = requirements_file.read_text(encoding="utf-8")
            project_dir = self.config.projects_dir / project_id
            policy = resolve_effective_policy(project_policy=None, grant=None)
            scrum_agent = SoftwareDevelopmentAgent(provider=_clone_provider(self.provider))
            _ = scrum_agent.run_scrum_cycle(requirements=requirements, output_dir=project_dir)
            engineering = EngineeringAgent(provider=self.provider)
            _ = engineering.handle(
                context=_build_agent_context(
                    project_id,
                    project_dir,
                    policy,
                    self.audit_logger,
                    metadata={
                        "requirements": requirements,
                        "output_dir": project_dir,
                    },
                ),
                order=None,
            )
            self.registry.register_project(
                project_id=project_id,
                name=project_id,
                domain="autonomous",
                platforms=["cli_tool"],
                metadata={"local_path": str(project_dir)},
            )
            _ = self.release_manager.create_release(
                project_dir=project_dir,
                project_id=project_id,
                version="0.1.0",
                tag=None,
            )
            deploy_order = {
                "environment": self.config.environment,
                "target": self.config.deploy_target,
                "execute": self.config.execute_deploy,
                "registry": self.registry,
            }
            security_decision = self.security_agent.handle(
                _build_agent_context(project_id, project_dir, policy, self.audit_logger),
                order=_build_work_order(
                    "security",
                    "gate_deploy",
                    {"environment": self.config.environment},
                ),
            )
            if security_decision.halted:
                raise RuntimeError(f"Deploy blocked: {security_decision.escalations}")
            self.operations_agent.handle(
                _build_agent_context(project_id, project_dir, policy, self.audit_logger),
                order=_build_work_order("operations", "deploy", deploy_order),
            )
            processed.append(project_id)
            _archive_requirements(requirements_file)

        if self.config.incident_signals_path and self.config.incident_signals_path.exists():
            self._process_incident_signals()

        return processed

    def _process_incident_signals(self) -> None:
        """Process incident signal file and heal projects."""
        if self.config.incident_signals_path is None:
            raise ValueError("Incident signals path is not configured.")
        payload = json.loads(self.config.incident_signals_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("Incident signals file must contain a JSON list.")
        for signal in payload:
            project_id = signal["project_id"]
            incident = self.incident_engine.create_incident(
                project_id=project_id,
                source=signal.get("source", "daemon"),
                severity=signal.get("severity", "medium"),
                signal_summary=signal.get("summary", "incident"),
                proposed_fix=signal.get("proposed_fix", "apply patch"),
            )
            self.incident_engine.heal_project(
                project_ref=project_id,
                incident_id=incident.incident_id,
                auto_push=False,
                deploy_target=self.config.deploy_target,
                environment=self.config.environment,
                execute_deploy=False,
            )


def _archive_requirements(path: Path) -> None:
    """Move processed requirements to an archive folder."""
    archive_dir = path.parent / "processed"
    archive_dir.mkdir(parents=True, exist_ok=True)
    target = archive_dir / path.name
    path.replace(target)


def _build_agent_context(
    project_id: str,
    project_dir: Path,
    policy: EffectivePolicy,
    audit_logger: AuditLogger,
    metadata: dict[str, Any] | None = None,
) -> AgentContext:
    return AgentContext(
        project_id=project_id,
        project_dir=project_dir,
        policy=policy,
        grant=None,
        audit_logger=audit_logger,
        metadata=metadata or {},
    )


def _build_work_order(department: str, action: str, payload: dict[str, Any]) -> WorkOrder:
    return WorkOrder(department=department, action=action, payload=payload)


def _clone_provider(provider: LLMProvider) -> LLMProvider:
    """Clone providers that should not share state across workflows."""
    if isinstance(provider, MockProvider):
        return MockProvider(provider._responses)
    return provider
