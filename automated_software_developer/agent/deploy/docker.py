"""Docker deployment target plugin."""

from __future__ import annotations

import shutil
import subprocess  # nosec B404
from pathlib import Path

from automated_software_developer.agent.deploy.base import (
    DeploymentResult,
    DeploymentTarget,
    utc_now,
)


class DockerDeploymentTarget(DeploymentTarget):
    """Docker deployment target with scaffold-first default behavior."""

    target_id = "docker"
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
        """Deploy project using Docker or scaffold instructions when not executing."""
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

        docker_path = shutil.which("docker")
        if execute and docker_path is not None:
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
                        "Docker build failed. "
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
                message=f"Docker image built: {image_tag}",
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
            message=(
                "Docker deployment scaffold generated. "
                "Run with --execute once credentials/registry access are configured."
            ),
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
        """Rollback docker deployment by documenting rollback intent."""
        del execute
        marker = project_dir / ".autosd" / "rollback-docker.txt"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(
            f"Rollback requested for {environment} at version {version}.\n",
            encoding="utf-8",
        )
        return DeploymentResult(
            project_id=project_dir.name,
            environment=environment,
            target=self.target_id,
            success=True,
            version=version,
            message="Docker rollback marker written.",
            deployed_at=utc_now(),
            strategy="standard",
            scaffold_only=True,
        )
