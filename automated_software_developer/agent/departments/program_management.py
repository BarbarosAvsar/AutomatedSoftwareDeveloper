"""Program management department agent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from automated_software_developer.agent.departments.base import AgentContext, AgentResult, WorkOrder
from automated_software_developer.agent.departments.policy import DepartmentPolicy
from automated_software_developer.agent.policy.engine import evaluate_action


@dataclass(frozen=True)
class WorkRequest:
    """Incoming work request to be routed by program management."""

    action: str
    payload: dict[str, Any]


class ProgramManagementAgent:
    """Program management agent for routing and governance."""

    department = "program_management"

    def __init__(self, policy: DepartmentPolicy | None = None) -> None:
        """Initialize program management agent with department policy."""
        self.policy = policy or DepartmentPolicy()

    def plan_work(self, context: AgentContext, requests: list[WorkRequest]) -> AgentResult:
        """Plan and route work orders from incoming requests."""
        orders: list[WorkOrder] = []
        escalations: list[str] = []
        halted = False

        for request in requests:
            if request.action == "deploy":
                env = request.payload.get("environment", "staging")
                decision = evaluate_action(policy=context.policy, action="deploy", environment=env)
                if not decision.allowed:
                    escalations.append(decision.reason)
                    halted = True
                    continue
                orders.append(
                    WorkOrder(
                        department="operations",
                        action="deploy",
                        payload=request.payload,
                    )
                )
            elif request.action == "release":
                orders.append(
                    WorkOrder(
                        department="operations",
                        action="release",
                        payload=request.payload,
                    )
                )
            elif request.action == "triage":
                orders.append(
                    WorkOrder(
                        department="support_ops",
                        action="triage",
                        payload=request.payload,
                    )
                )
            elif request.action == "ingest_corpus":
                orders.append(
                    WorkOrder(
                        department="data_intelligence",
                        action="ingest_corpus",
                        payload=request.payload,
                    )
                )
            elif request.action == "implement":
                orders.append(
                    WorkOrder(
                        department="engineering",
                        action="implement",
                        payload=request.payload,
                    )
                )
            else:
                escalations.append(f"unknown_request:{request.action}")

        return AgentResult(
            department=self.department,
            actions=["plan_work"],
            artifacts=[],
            gates_run=["policy"],
            next_steps=["execute_orders"],
            escalations=escalations,
            metadata={"orders": orders},
            halted=halted,
        )

    def handle(self, context: AgentContext, order: WorkOrder | None = None) -> AgentResult:
        """Program management handle hook for protocol compliance."""
        raise ValueError("ProgramManagementAgent does not execute work orders directly.")
