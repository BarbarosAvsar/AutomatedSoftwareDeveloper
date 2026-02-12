"""Scaffold-only platform adapters for desktop and mobile targets."""

from __future__ import annotations

from pathlib import Path

from automated_software_developer.agent.models import RefinedRequirements
from automated_software_developer.agent.platforms.base import PlatformAdapter


class DesktopAppAdapter(PlatformAdapter):
    """Packaging-focused desktop adapter with conservative defaults."""

    adapter_id = "desktop_app"
    description = "Desktop app adapter (packaging scaffold only)."

    def score(self, refined: RefinedRequirements) -> int:
        """Return heuristic score for desktop-oriented requests."""
        text = _requirements_text(refined)
        return 2 if "desktop" in text else 0

    def rationale(self, refined: RefinedRequirements) -> str:
        """Return rationale for desktop scaffold selection."""
        return (
            "Desktop adapter selected for packaging scaffold generation only; "
            "runtime binaries require platform-specific credentials and build chains."
        )

    def supported_deploy_targets(self) -> list[str]:
        """Return desktop artifact deploy targets."""
        return ["github_release", "generic_container_ci"]

    def build_commands(self, project_dir: Path) -> list[str]:
        """Return conservative build command placeholders."""
        return ["python -m compileall -q ."]

    def package_commands(self, project_dir: Path) -> list[str]:
        """Return scaffold-only packaging command placeholders."""
        return ["python -m compileall -q ."]

    def minimum_test_patterns(self) -> list[str]:
        """Return minimal desktop adapter test pattern requirements."""
        return ["tests/test_*.py"]

    def telemetry_hooks(self) -> list[str]:
        """Return privacy-safe desktop telemetry hooks."""
        return ["app_launch_count", "crash_count"]

    def scaffold_files(self, project_name: str) -> dict[str, str]:
        """Return desktop packaging scaffold notes."""
        return {
            "desktop/README.md": (
                f"# {project_name} Desktop\n\n"
                "Desktop packaging scaffold only. Configure signing and installers in CI.\n"
            ),
        }


class MobileAppAdapter(PlatformAdapter):
    """CI-focused mobile adapter with publishing disabled by default."""

    adapter_id = "mobile_app"
    description = "Mobile app adapter (CI scaffold only)."

    def score(self, refined: RefinedRequirements) -> int:
        """Return heuristic score for mobile-oriented requests."""
        text = _requirements_text(refined)
        return 2 if "mobile" in text else 0

    def rationale(self, refined: RefinedRequirements) -> str:
        """Return rationale for mobile scaffold selection."""
        return (
            "Mobile adapter selected for CI scaffold generation only; app store "
            "publishing stays policy-gated and credential-dependent."
        )

    def supported_deploy_targets(self) -> list[str]:
        """Return mobile deploy targets (policy-gated)."""
        return ["app_store", "play_store", "generic_container_ci"]

    def build_commands(self, project_dir: Path) -> list[str]:
        """Return conservative command placeholders for mobile build stage."""
        return ["python -m compileall -q ."]

    def package_commands(self, project_dir: Path) -> list[str]:
        """Return scaffold-only packaging commands for mobile builds."""
        return ["python -m compileall -q ."]

    def minimum_test_patterns(self) -> list[str]:
        """Return minimum mobile adapter test pattern requirements."""
        return ["tests/test_*.py", "tests/mobile/test_*.py"]

    def telemetry_hooks(self) -> list[str]:
        """Return privacy-safe mobile telemetry hooks."""
        return ["session_count", "crash_count", "screen_load_ms"]

    def scaffold_files(self, project_name: str) -> dict[str, str]:
        """Return mobile CI scaffold files."""
        return {
            "mobile/README.md": (
                f"# {project_name} Mobile\n\n"
                "Mobile CI scaffold only. Configure signing keys outside repository.\n"
            ),
        }


def _requirements_text(refined: RefinedRequirements) -> str:
    """Return lowercase aggregate text for adapter heuristic scoring."""
    story_text = "\n".join(item.story for item in refined.stories)
    return f"{refined.product_brief}\n{story_text}".lower()
