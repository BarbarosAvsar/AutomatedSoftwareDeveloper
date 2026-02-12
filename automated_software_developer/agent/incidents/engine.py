"""Incident detection and autonomous self-healing engine."""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from automated_software_developer.agent.deploy.base import DeploymentOrchestrator, DeploymentResult
from automated_software_developer.agent.incidents.model import (
    IncidentRecord,
    append_incident,
    load_incidents,
)
from automated_software_developer.agent.patching import PatchEngine, PatchOutcome
from automated_software_developer.agent.portfolio.registry import PortfolioRegistry
from automated_software_developer.logging_utils import get_logger

AUTOSD_INCIDENTS_PATH_ENV = "AUTOSD_INCIDENTS_PATH"
LOGGER = get_logger()


@dataclass(frozen=True)
class HealingResult:
    """Result of one incident healing attempt."""

    incident: IncidentRecord
    patch_outcome: PatchOutcome
    deploy_outcome: DeploymentResult | None
    rollback_attempted: bool


class IncidentEngine:
    """Creates incident records and drives self-healing workflow."""

    def __init__(
        self,
        *,
        registry: PortfolioRegistry,
        patch_engine: PatchEngine,
        deployment_orchestrator: DeploymentOrchestrator | None = None,
        incidents_path: Path | None = None,
    ) -> None:
        """Initialize incident engine dependencies and storage path."""
        self.registry = registry
        self.patch_engine = patch_engine
        self.deployment_orchestrator = deployment_orchestrator
        self.incidents_path = (incidents_path or _default_incidents_path()).expanduser().resolve()
        self.incidents_path.parent.mkdir(parents=True, exist_ok=True)

    def detect_from_signals(
        self,
        *,
        project_id: str,
        error_count: int,
        crash_count: int,
    ) -> IncidentRecord | None:
        """Create incident when telemetry signal thresholds are crossed."""
        if error_count < 5 and crash_count < 1:
            return None
        severity = "high" if crash_count > 0 else "medium"
        summary = f"error_count={error_count}, crash_count={crash_count}"
        LOGGER.warning(
            "Incident detected from telemetry signals",
            extra={
                "project_id": project_id,
                "error_count": error_count,
                "crash_count": crash_count,
                "severity": severity,
            },
        )
        return self.create_incident(
            project_id=project_id,
            source="telemetry",
            severity=severity,
            signal_summary=summary,
            proposed_fix="Investigate failing path and add regression tests before redeploy.",
        )

    def create_incident(
        self,
        *,
        project_id: str,
        source: str,
        severity: str,
        signal_summary: str,
        proposed_fix: str | None,
    ) -> IncidentRecord:
        """Create and persist a new incident record."""
        record = IncidentRecord.create(
            project_id=project_id,
            source=source,
            severity=severity,
            signal_summary=signal_summary,
            proposed_fix=proposed_fix,
        )
        append_incident(self.incidents_path, record)
        LOGGER.info(
            "Incident recorded",
            extra={
                "project_id": project_id,
                "incident_id": record.incident_id,
                "source": source,
                "severity": severity,
            },
        )
        return record

    def list_incidents(self, project_id: str | None = None) -> list[IncidentRecord]:
        """Return latest incident records optionally filtered by project id."""
        latest: dict[str, IncidentRecord] = {}
        for record in load_incidents(self.incidents_path):
            latest[record.incident_id] = record
        records = list(latest.values())
        if project_id is not None:
            records = [record for record in records if record.project_id == project_id]
        return sorted(records, key=lambda item: (item.created_at, item.incident_id))

    def get_incident(self, incident_id: str) -> IncidentRecord | None:
        """Return one incident by identifier."""
        for record in self.list_incidents():
            if record.incident_id == incident_id:
                return record
        return None

    def heal_project(
        self,
        *,
        project_ref: str,
        incident_id: str | None,
        auto_push: bool,
        deploy_target: str | None,
        environment: str,
        execute_deploy: bool,
    ) -> HealingResult:
        """Run incident-driven self-healing flow using patch + optional deploy."""
        entry = self.registry.get(project_ref)
        if entry is None:
            raise KeyError(f"Project '{project_ref}' not found.")

        incident = self._resolve_or_create_incident(entry.project_id, incident_id)
        LOGGER.info(
            "Healing initiated",
            extra={
                "project_id": entry.project_id,
                "incident_id": incident.incident_id,
                "deploy_target": deploy_target,
                "environment": environment,
                "auto_push": auto_push,
                "execute_deploy": execute_deploy,
            },
        )
        reason = (
            f"incident {incident.incident_id}: {incident.signal_summary}. "
            f"{incident.proposed_fix or 'Apply risk-reduced fix and add regression checks.'}"
        )
        patch_outcome = self.patch_engine.patch_project(
            entry.project_id,
            reason=reason,
            auto_push=auto_push,
            create_tag=False,
        )

        deploy_outcome: DeploymentResult | None = None
        rollback_attempted = False
        if patch_outcome.success and deploy_target is not None:
            if self.deployment_orchestrator is None:
                raise RuntimeError("Deployment orchestrator is not configured for heal operation.")
            deploy_outcome = self.deployment_orchestrator.deploy(
                project_ref=entry.project_id,
                environment=environment,
                target=deploy_target,
                strategy="canary",
                execute=execute_deploy,
            )
            if not deploy_outcome.success:
                rollback_attempted = True
                self.deployment_orchestrator.rollback(
                    project_ref=entry.project_id,
                    environment=environment,
                    target=deploy_target,
                    execute=False,
                )

        status = "resolved"
        if not patch_outcome.success or (deploy_outcome is not None and not deploy_outcome.success):
            status = "failed"

        project_dir = _resolve_project_dir(entry.metadata)
        postmortem_path = self._write_postmortem(
            project_dir=project_dir,
            incident=incident,
            patch_outcome=patch_outcome,
            deploy_outcome=deploy_outcome,
            rollback_attempted=rollback_attempted,
            status=status,
        )

        updated = replace(
            incident,
            updated_at=_utc_now(),
            status=status,
            patch_success=patch_outcome.success,
            deploy_success=deploy_outcome.success if deploy_outcome is not None else None,
            postmortem_path=str(postmortem_path),
        )
        append_incident(self.incidents_path, updated)
        LOGGER.info(
            "Healing complete",
            extra={
                "project_id": entry.project_id,
                "incident_id": incident.incident_id,
                "status": status,
                "patch_success": patch_outcome.success,
                "deploy_success": deploy_outcome.success if deploy_outcome is not None else None,
            },
        )
        return HealingResult(
            incident=updated,
            patch_outcome=patch_outcome,
            deploy_outcome=deploy_outcome,
            rollback_attempted=rollback_attempted,
        )

    def _resolve_or_create_incident(
        self,
        project_id: str,
        incident_id: str | None,
    ) -> IncidentRecord:
        """Resolve provided incident id or create a synthetic operational incident."""
        if incident_id is not None:
            record = self.get_incident(incident_id)
            if record is None:
                raise KeyError(f"Incident '{incident_id}' not found.")
            if record.project_id != project_id:
                raise ValueError(
                    f"Incident '{incident_id}' belongs to '{record.project_id}', "
                    f"not '{project_id}'."
                )
            return record
        return self.create_incident(
            project_id=project_id,
            source="manual_heal",
            severity="medium",
            signal_summary="Manual healing requested.",
            proposed_fix="Run bounded patch workflow and redeploy safely.",
        )

    def _write_postmortem(
        self,
        *,
        project_dir: Path,
        incident: IncidentRecord,
        patch_outcome: PatchOutcome,
        deploy_outcome: DeploymentResult | None,
        rollback_attempted: bool,
        status: str,
    ) -> Path:
        """Write incident postmortem into project artifact directory."""
        postmortem_dir = project_dir / ".autosd" / "postmortems"
        postmortem_dir.mkdir(parents=True, exist_ok=True)
        postmortem_path = postmortem_dir / f"{incident.incident_id}.md"
        lines = [
            f"# Postmortem {incident.incident_id}",
            "",
            f"Project: {incident.project_id}",
            f"Status: {status}",
            f"Created: {incident.created_at}",
            f"Updated: {_utc_now()}",
            f"Source: {incident.source}",
            f"Severity: {incident.severity}",
            f"Signal: {incident.signal_summary}",
            "",
            "## Patch",
            f"- Success: {patch_outcome.success}",
            f"- Branch: {patch_outcome.branch}",
            f"- Commit: {patch_outcome.commit_sha}",
            f"- Error: {patch_outcome.error}",
            "",
            "## Deploy",
            f"- Attempted: {deploy_outcome is not None}",
            f"- Success: {deploy_outcome.success if deploy_outcome else 'n/a'}",
            f"- Rollback Attempted: {rollback_attempted}",
            f"- Message: {deploy_outcome.message if deploy_outcome else 'n/a'}",
        ]
        postmortem_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return postmortem_path


def _default_incidents_path() -> Path:
    """Resolve default incidents JSONL storage path."""
    env_value = os.environ.get(AUTOSD_INCIDENTS_PATH_ENV)
    if env_value:
        return Path(env_value)
    return Path.home() / ".autosd" / "incidents.jsonl"


def _resolve_project_dir(metadata: dict[str, str]) -> Path:
    """Resolve project directory from registry metadata values."""
    for key in ("local_path", "workspace_path", "project_path"):
        value = metadata.get(key)
        if value is None:
            continue
        candidate = Path(value).expanduser().resolve()
        if candidate.exists() and candidate.is_dir():
            return candidate
    raise RuntimeError("No valid local project path found in registry metadata.")


def _utc_now() -> str:
    """Return UTC timestamp in ISO format."""
    return datetime.now(tz=UTC).isoformat()
