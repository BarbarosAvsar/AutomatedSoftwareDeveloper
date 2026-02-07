"""Company orchestrator coordinating department agents."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from automated_software_developer.agent.audit import AuditLogger
from automated_software_developer.agent.departments.base import (
    AgentContext,
    AgentResult,
    WorkOrder,
)
from automated_software_developer.agent.departments.data_intelligence import DataIntelligenceAgent
from automated_software_developer.agent.departments.engineering import EngineeringAgent
from automated_software_developer.agent.departments.operations import OperationsAgent
from automated_software_developer.agent.departments.policy import DepartmentPolicy
from automated_software_developer.agent.departments.program_management import (
    ProgramManagementAgent,
    WorkRequest,
)
from automated_software_developer.agent.departments.security import SecurityAgent
from automated_software_developer.agent.departments.support_ops import SupportOpsAgent
from automated_software_developer.agent.policy.engine import EffectivePolicy
from automated_software_developer.agent.providers.base import LLMProvider


@dataclass(frozen=True)
class CompanyContext:
    """Context for a company orchestration run."""

    project_id: str
    project_dir: Path
    policy: EffectivePolicy
    requirements: str | None = None
    registry: Any | None = None
    audit_logger: AuditLogger | None = None
    grant: Any | None = None
    metadata: dict[str, Any] | None = None


class CompanyOrchestrator:
    """Thin orchestrator that routes work to department agents."""

    def __init__(
        self,
        *,
        provider: LLMProvider,
        department_policy: DepartmentPolicy | None = None,
    ) -> None:
        """Initialize orchestrator with department agents."""
        self.department_policy = department_policy or DepartmentPolicy()
        self.pmo = ProgramManagementAgent(policy=self.department_policy)
        self.security = SecurityAgent(policy=self.department_policy)
        self.engineering = EngineeringAgent(provider=provider)
        self.operations = OperationsAgent(audit_logger=AuditLogger())
        self.data = DataIntelligenceAgent(policy=self.department_policy)
        self.support = SupportOpsAgent()

    def run(self, context: CompanyContext, requests: list[WorkRequest]) -> list[AgentResult]:
        """Run a set of work requests through PMO routing and department execution."""
        audit_logger = context.audit_logger or AuditLogger()
        agent_context = AgentContext(
            project_id=context.project_id,
            project_dir=context.project_dir,
            policy=context.policy,
            grant=context.grant,
            audit_logger=audit_logger,
            metadata=context.metadata or {},
        )
        plan_result = self.pmo.plan_work(agent_context, requests)
        results = [plan_result]
        if plan_result.halted:
            return results

        orders: list[WorkOrder] = plan_result.metadata.get("orders", [])
        for order in orders:
            results.append(self._dispatch(agent_context, order))
        return results

    def _dispatch(self, context: AgentContext, order: WorkOrder) -> AgentResult:
        """Dispatch a work order to the matching department."""
        if order.department == "security":
            return self.security.handle(context, order)
        if order.department == "engineering":
            return self.engineering.handle(context, order)
        if order.department == "operations":
            return self.operations.handle(context, order)
        if order.department == "data_intelligence":
            return self.data.handle(context, order)
        if order.department == "support_ops":
            return self.support.handle(context, order)
        raise ValueError(f"Unknown department: {order.department}")
