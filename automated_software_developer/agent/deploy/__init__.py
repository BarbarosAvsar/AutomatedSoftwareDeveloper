"""Deployment targets and orchestrator exports."""

from __future__ import annotations

from automated_software_developer.agent.deploy.base import (
    DeploymentOrchestrator,
    DeploymentResult,
    DeploymentTarget,
)
from automated_software_developer.agent.deploy.docker import DockerDeploymentTarget
from automated_software_developer.agent.deploy.generic_container import (
    GenericContainerDeploymentTarget,
)
from automated_software_developer.agent.deploy.github_pages import GitHubPagesDeploymentTarget


def default_deployment_targets() -> dict[str, DeploymentTarget]:
    """Return default deployment target plugin instances."""
    targets = [
        DockerDeploymentTarget(),
        GitHubPagesDeploymentTarget(),
        GenericContainerDeploymentTarget(),
    ]
    return {item.target_id: item for item in targets}


__all__ = [
    "DeploymentOrchestrator",
    "DeploymentResult",
    "DockerDeploymentTarget",
    "GitHubPagesDeploymentTarget",
    "GenericContainerDeploymentTarget",
    "default_deployment_targets",
]
