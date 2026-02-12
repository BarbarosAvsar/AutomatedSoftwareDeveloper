"""GitHub Pages deployment target plugin."""

from __future__ import annotations

from pathlib import Path

from automated_software_developer.agent.deploy.base import (
    DeploymentResult,
    DeploymentTarget,
    utc_now,
)

PAGES_WORKFLOW = (
    """
name: Deploy Pages

on:
  workflow_dispatch:
  push:
    branches: [main, master]

permissions:
  contents: read
  pages: write
  id-token: write

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5
      - uses: actions/configure-pages@983d7736d9b0ae728b81ab479565c72886d7745b
      - uses: actions/upload-pages-artifact@56afc609e74202658d3ffba0e8f6dda462b719fa
        with:
          path: .
      - uses: actions/deploy-pages@d6db90164ac5ed86f2b6aed7e0febac5b3c0c03e
""".strip()
    + "\n"
)


class GitHubPagesDeploymentTarget(DeploymentTarget):
    """GitHub Pages deployment target using workflow scaffolding."""

    target_id = "github_pages"
    supports_canary = False

    def deploy(
        self,
        *,
        project_dir: Path,
        environment: str,
        version: str,
        strategy: str,
        execute: bool,
    ) -> DeploymentResult:
        """Create GitHub Pages workflow and optionally execute via instructions."""
        del execute, strategy
        workflow_path = project_dir / ".github" / "workflows" / "deploy-pages.yml"
        workflow_path.parent.mkdir(parents=True, exist_ok=True)
        workflow_path.write_text(PAGES_WORKFLOW, encoding="utf-8")
        index = project_dir / "index.html"
        if not index.exists():
            index.write_text(
                "<html><body><h1>Generated Site</h1></body></html>\n",
                encoding="utf-8",
            )
        return DeploymentResult(
            project_id=project_dir.name,
            environment=environment,
            target=self.target_id,
            success=True,
            version=version,
            message="GitHub Pages workflow scaffolded.",
            deployed_at=utc_now(),
            strategy="standard",
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
        """Record rollback marker for pages deployment."""
        del execute
        marker = project_dir / ".autosd" / "rollback-pages.txt"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(
            f"GitHub Pages rollback requested for {environment} at {version}.\n",
            encoding="utf-8",
        )
        return DeploymentResult(
            project_id=project_dir.name,
            environment=environment,
            target=self.target_id,
            success=True,
            version=version,
            message="GitHub Pages rollback marker written.",
            deployed_at=utc_now(),
            strategy="standard",
            scaffold_only=True,
        )
