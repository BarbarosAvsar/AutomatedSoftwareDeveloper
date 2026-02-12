"""Platform adapter interfaces and capability graph helpers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from automated_software_developer.agent.models import RefinedRequirements


@dataclass(frozen=True)
class PlatformPlan:
    """Adapter selection result with build/package/deploy capabilities."""

    adapter_id: str
    rationale: str
    supported_deploy_targets: list[str]
    build_commands: list[str]
    package_commands: list[str]
    minimum_test_patterns: list[str]
    telemetry_hooks: list[str]
    scaffold_files: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        """Serialize platform plan for JSON artifacts."""
        return {
            "adapter_id": self.adapter_id,
            "rationale": self.rationale,
            "supported_deploy_targets": self.supported_deploy_targets,
            "build_commands": self.build_commands,
            "package_commands": self.package_commands,
            "minimum_test_patterns": self.minimum_test_patterns,
            "telemetry_hooks": self.telemetry_hooks,
            "scaffold_files": self.scaffold_files,
        }


class PlatformAdapter(ABC):
    """Abstract adapter contract for platform-oriented generation."""

    adapter_id: str
    description: str

    @abstractmethod
    def score(self, refined: RefinedRequirements) -> int:
        """Score how well adapter matches refined requirements."""

    @abstractmethod
    def rationale(self, refined: RefinedRequirements) -> str:
        """Return deterministic rationale for adapter selection."""

    @abstractmethod
    def supported_deploy_targets(self) -> list[str]:
        """Return deployment targets supported by this adapter."""

    @abstractmethod
    def build_commands(self, project_dir: Path) -> list[str]:
        """Return build commands for this adapter."""

    @abstractmethod
    def package_commands(self, project_dir: Path) -> list[str]:
        """Return packaging commands for this adapter."""

    @abstractmethod
    def minimum_test_patterns(self) -> list[str]:
        """Return minimum expected test suite patterns."""

    @abstractmethod
    def telemetry_hooks(self) -> list[str]:
        """Return privacy-safe telemetry integration hooks."""

    @abstractmethod
    def scaffold_files(self, project_name: str) -> dict[str, str]:
        """Return optional scaffolding files for generated project."""

    def build_plan(self, refined: RefinedRequirements, project_dir: Path) -> PlatformPlan:
        """Build concrete platform plan for selected adapter."""
        return PlatformPlan(
            adapter_id=self.adapter_id,
            rationale=self.rationale(refined),
            supported_deploy_targets=self.supported_deploy_targets(),
            build_commands=self.build_commands(project_dir),
            package_commands=self.package_commands(project_dir),
            minimum_test_patterns=self.minimum_test_patterns(),
            telemetry_hooks=self.telemetry_hooks(),
            scaffold_files=self.scaffold_files(refined.project_name),
        )


@dataclass(frozen=True)
class CapabilityGraph:
    """Simple capability graph mapping adapters to deployment targets."""

    adapters: dict[str, dict[str, object]]

    def to_dict(self) -> dict[str, object]:
        """Serialize capability graph for artifact persistence."""
        return {
            "adapters": self.adapters,
        }
