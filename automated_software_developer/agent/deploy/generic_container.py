"""Generic container CI deployment target plugin."""

from __future__ import annotations

from pathlib import Path

from automated_software_developer.agent.deploy.base import (
    DeploymentResult,
    DeploymentTarget,
    utc_now,
)

GENERIC_CONTAINER_WORKFLOW = """
name: Container Build

on:
  workflow_dispatch:
  push:
    branches: [main, master]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build container
        run: |
          if [ -f Dockerfile ]; then
            docker build -t autosd/app:${{ github.sha }} .
          else
            echo "No Dockerfile; skipping build"
          fi
""".strip() + "\n"


class GenericContainerDeploymentTarget(DeploymentTarget):
    """Generic container target that scaffolds CI workflow."""

    target_id = "generic_container"
    supports_canary = True

    def deploy(
        self,
        *,
        project_dir: Path,
        environment: str,
        version: str,
        strategy: str,
        execute: bool,
    ) -> DeploymentResult:
        """Scaffold container workflow and deployment notes."""
        del execute
        workflow_path = project_dir / ".github" / "workflows" / "deploy-container.yml"
        workflow_path.parent.mkdir(parents=True, exist_ok=True)
        workflow_path.write_text(GENERIC_CONTAINER_WORKFLOW, encoding="utf-8")
        notes_path = project_dir / ".autosd" / "deploy-container-notes.md"
        notes_path.parent.mkdir(parents=True, exist_ok=True)
        notes_path.write_text(
            "\n".join(
                [
                    "# Generic Container Deploy",
                    "",
                    f"Environment: {environment}",
                    f"Version: {version}",
                    f"Strategy: {strategy}",
                    "",
                    "This target generates CI scaffolding only by default.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        return DeploymentResult(
            project_id=project_dir.name,
            environment=environment,
            target=self.target_id,
            success=True,
            version=version,
            message="Generic container workflow scaffolded.",
            deployed_at=utc_now(),
            strategy=strategy,
            scaffold_only=True,
        )

    def rollback(
        self,
        *,
        project_dir: Path,
        environment: str,
        version: str,
        execute: bool,
    ) -> DeploymentResult:
        """Record generic container rollback marker."""
        del execute
        marker = project_dir / ".autosd" / "rollback-container.txt"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(
            f"Rollback requested for container target in {environment} at {version}.\n",
            encoding="utf-8",
        )
        return DeploymentResult(
            project_id=project_dir.name,
            environment=environment,
            target=self.target_id,
            success=True,
            version=version,
            message="Container rollback marker written.",
            deployed_at=utc_now(),
            strategy="standard",
            scaffold_only=True,
        )
