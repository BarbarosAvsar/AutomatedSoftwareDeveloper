"""Engineering department agent implementation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from automated_software_developer.agent.departments.base import AgentContext, AgentResult, WorkOrder
from automated_software_developer.agent.orchestrator import AgentConfig, SoftwareDevelopmentAgent
from automated_software_developer.agent.providers.base import LLMProvider


@dataclass(frozen=True)
class EngineeringOutcome:
    """Outcome summary for engineering work execution."""

    project_name: str
    output_dir: Path
    verification_commands: list[str]


class EngineeringAgent:
    """Engineering department agent for implementation and architecture artifacts."""

    department = "engineering"

    def __init__(self, provider: LLMProvider, config: AgentConfig | None = None) -> None:
        """Initialize with LLM provider and optional config override."""
        self.provider = provider
        self.config = config or AgentConfig()
        self._agent = SoftwareDevelopmentAgent(provider=provider, config=self.config)

    def handle(self, context: AgentContext, order: WorkOrder | None = None) -> AgentResult:
        """Execute engineering work order or default to full implementation run."""
        payload = order.payload if order else context.metadata
        requirements = payload.get("requirements")
        output_dir = payload.get("output_dir", context.project_dir)
        if not isinstance(requirements, str) or not requirements.strip():
            raise ValueError("EngineeringAgent requires non-empty requirements text.")
        output_path = Path(output_dir)

        summary = self._agent.run(requirements=requirements, output_dir=output_path)
        outcome = EngineeringOutcome(
            project_name=summary.project_name,
            output_dir=summary.output_dir,
            verification_commands=[result.command for result in summary.verification_results],
        )
        artifacts = [
            summary.refined_spec_path,
            summary.backlog_path,
            summary.design_doc_path,
            summary.sprint_log_path,
            summary.platform_plan_path,
            summary.capability_graph_path,
            summary.architecture_doc_path,
            summary.architecture_components_path,
            summary.architecture_adrs_path,
            summary.build_hash_path,
        ]
        return AgentResult(
            department=self.department,
            actions=["implement_requirements", "generate_architecture", "run_quality_gates"],
            artifacts=[path for path in artifacts if path is not None],
            gates_run=["quality_gates", "security_scan", "architecture"],
            next_steps=["hand_off_build_specs"],
            escalations=[],
            metadata={"outcome": outcome},
        )
