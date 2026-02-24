"""Generic container CI deployment target plugin."""

from __future__ import annotations

import shutil
import subprocess  # nosec B404
from pathlib import Path

from automated_software_developer.agent.deploy.base import (
    DeploymentResult,
    DeploymentTarget,
    utc_now,
)

GENERIC_CONTAINER_WORKFLOW = (
    """
name: Container Build

on:
  workflow_dispatch:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5
      - name: Build container
        run: |
          if [ -f Dockerfile ]; then
            docker build -t autosd/app:${{ github.sha }} .
          else
            echo "No Dockerfile; skipping build"
          fi
""".strip()
    + "\n"
)


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
        workflow_path = project_dir / ".github" / "workflows" / "deploy-container.yml"
        workflow_path.parent.mkdir(parents=True, exist_ok=True)
        workflow_path.write_text(GENERIC_CONTAINER_WORKFLOW, encoding="utf-8")
        dockerfile = project_dir / "Dockerfile"
        if not dockerfile.exists():
            dockerfile.write_text(
                "\n".join(
                    [
                        "FROM python:3.12-slim",
                        "WORKDIR /app",
                        "COPY . .",
                        "RUN pip install --upgrade pip && pip install -e . || true",
                        'CMD ["python", "-m", "automated_software_developer", "--help"]',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

        if execute:
            docker_path = shutil.which("docker")
            if docker_path is None:
                return DeploymentResult(
                    project_id=project_dir.name,
                    environment=environment,
                    target=self.target_id,
                    success=False,
                    version=version,
                    message=(
                        "Execution requested, but Docker is unavailable on PATH. "
                        "Install Docker or run without --execute."
                    ),
                    deployed_at=utc_now(),
                    strategy=strategy,
                    scaffold_only=False,
                )
            image_tag = f"autosd/{project_dir.name}:{version}"
            completed = subprocess.run(  # nosec B603
                [docker_path, "build", "-t", image_tag, "."],
                cwd=str(project_dir),
                text=True,
                capture_output=True,
                check=False,
            )
            if completed.returncode != 0:
                return DeploymentResult(
                    project_id=project_dir.name,
                    environment=environment,
                    target=self.target_id,
                    success=False,
                    version=version,
                    message=(
                        "Container build failed. "
                        f"stdout={completed.stdout.strip()} stderr={completed.stderr.strip()}"
                    ),
                    deployed_at=utc_now(),
                    strategy=strategy,
                    scaffold_only=False,
                )
            return DeploymentResult(
                project_id=project_dir.name,
                environment=environment,
                target=self.target_id,
                success=True,
                version=version,
                message=f"Container image built: {image_tag}",
                deployed_at=utc_now(),
                strategy=strategy,
                scaffold_only=False,
            )

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
