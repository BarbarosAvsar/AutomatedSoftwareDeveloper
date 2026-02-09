"""Platform and operations department agent."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from automated_software_developer.agent.audit import AuditLogger
from automated_software_developer.agent.departments.base import (
    AgentContext,
    AgentResult,
    WorkOrder,
)
from automated_software_developer.agent.deploy import (
    DeploymentOrchestrator,
    default_deployment_targets,
)
from automated_software_developer.agent.gitops import GitOpsManager
from automated_software_developer.agent.provenance import (
    BuildManifest,
    gather_tool_versions,
    write_build_manifest,
)
from automated_software_developer.agent.reproducibility import (
    build_artifact_checksums,
    write_build_hash,
)
from automated_software_developer.agent.security import scan_workspace_for_secrets


@dataclass(frozen=True)
class ReleaseBundle:
    """Release bundle metadata output."""

    release_id: str
    release_dir: Path
    manifest_path: Path
    build_manifest_path: Path
    tag: str | None
    commit_sha: str | None


class ReleaseManager:
    """Create release bundles and provenance artifacts."""

    def __init__(self, gitops: GitOpsManager | None = None) -> None:
        """Initialize release manager with gitops helper."""
        self.gitops = gitops or GitOpsManager()

    def create_release(
        self,
        *,
        project_dir: Path,
        project_id: str,
        version: str,
        tag: str | None,
    ) -> ReleaseBundle:
        """Create a release bundle under .autosd/releases."""
        if not project_dir.exists():
            raise FileNotFoundError(f"Project directory not found: {project_dir}")
        scan = scan_workspace_for_secrets(project_dir)
        if scan:
            findings = "\n".join(scan)
            raise RuntimeError(f"Potential secrets detected before release:\n{findings}")

        build_manifest_path = project_dir / ".autosd" / "provenance" / "build_manifest.json"
        if not build_manifest_path.exists():
            manifest = BuildManifest(
                project_id=project_id,
                version=version,
                commit_sha=None,
                tag=tag,
                gates_run=[],
                gate_results=[],
                reproducible=False,
                tool_versions=gather_tool_versions(),
            )
            write_build_manifest(project_dir, manifest)

        release_id = datetime.now(tz=UTC).strftime("%Y%m%d%H%M%S")
        release_dir = project_dir / ".autosd" / "releases" / release_id
        release_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = release_dir / "release.json"

        commit_sha = None
        if tag is not None:
            self.gitops.ensure_repository(project_dir)
            self.gitops.commit_push_tag(
                repo_dir=project_dir,
                message=f"chore(release): {version}",
                branch=None,
                auto_push=False,
                tag=tag,
            )
            commit_sha = self.gitops.current_commit(project_dir)

        release_payload: dict[str, Any] = {
            "release_id": release_id,
            "project_id": project_id,
            "version": version,
            "created_at": datetime.now(tz=UTC).isoformat(),
            "build_manifest": str(build_manifest_path.relative_to(project_dir)),
            "tag": tag,
            "commit_sha": commit_sha,
        }
        manifest_path.write_text(json.dumps(release_payload, indent=2), encoding="utf-8")
        checksums = build_artifact_checksums(project_dir)
        write_build_hash(project_dir, checksums=checksums, seed=None, lockfiles=[])

        return ReleaseBundle(
            release_id=release_id,
            release_dir=release_dir,
            manifest_path=manifest_path,
            build_manifest_path=build_manifest_path,
            tag=tag,
            commit_sha=commit_sha,
        )


class OperationsAgent:
    """Operations agent for deployment, release, and runtime actions."""

    department = "operations"

    def __init__(
        self,
        *,
        audit_logger: AuditLogger | None = None,
        deploy_orchestrator: DeploymentOrchestrator | None = None,
        release_manager: ReleaseManager | None = None,
    ) -> None:
        """Initialize operations agent with dependencies."""
        self.audit_logger = audit_logger or AuditLogger()
        self.release_manager = release_manager or ReleaseManager()
        self.deploy_orchestrator = deploy_orchestrator

    def handle(self, context: AgentContext, order: WorkOrder | None = None) -> AgentResult:
        """Dispatch operations work order."""
        if order is None:
            raise ValueError("OperationsAgent requires a work order.")
        if order.action == "release":
            bundle = self.release_manager.create_release(
                project_dir=context.project_dir,
                project_id=context.project_id,
                version=order.payload.get("version", "0.1.0"),
                tag=order.payload.get("tag"),
            )
            self.audit_logger.log(
                project_id=context.project_id,
                action="release",
                result="ok",
                grant_id=context.grant.grant_id if context.grant else None,
                gates_run=["provenance"],
                commit_ref=bundle.commit_sha,
                tag_ref=bundle.tag,
                break_glass_used=False,
                details={"release_id": bundle.release_id},
            )
            return AgentResult(
                department=self.department,
                actions=["release"],
                artifacts=[bundle.release_dir, bundle.manifest_path, bundle.build_manifest_path],
                gates_run=["provenance"],
                next_steps=["deploy"],
                escalations=[],
                metadata={"bundle": bundle},
            )

        if order.action == "deploy":
            orchestrator = self.deploy_orchestrator or DeploymentOrchestrator(
                registry=order.payload["registry"],
                targets=default_deployment_targets(),
            )
            result = orchestrator.deploy(
                project_ref=context.project_id,
                environment=order.payload.get("environment", "staging"),
                target=order.payload.get("target", "generic_container"),
                strategy=order.payload.get("strategy", "standard"),
                execute=bool(order.payload.get("execute", False)),
            )
            self.audit_logger.log(
                project_id=context.project_id,
                action="deploy",
                result="ok" if result.success else "failed",
                grant_id=context.grant.grant_id if context.grant else None,
                gates_run=["deployment_policy"],
                commit_ref=None,
                tag_ref=None,
                break_glass_used=False,
                details={"environment": result.environment, "target": result.target},
            )
            return AgentResult(
                department=self.department,
                actions=["deploy"],
                artifacts=[],
                gates_run=["deployment_policy"],
                next_steps=[],
                escalations=[] if result.success else ["deploy_failed"],
                metadata={"deployment": result},
            )

        raise ValueError(f"Unknown operations action: {order.action}")
