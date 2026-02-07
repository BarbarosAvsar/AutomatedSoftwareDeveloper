"""Security and compliance department agent."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from automated_software_developer.agent.departments.base import AgentContext, AgentResult, WorkOrder
from automated_software_developer.agent.departments.policy import DepartmentPolicy
from automated_software_developer.agent.policy.engine import evaluate_action
from automated_software_developer.agent.preauth.verify import capability_allowed


@dataclass(frozen=True)
class SecurityGateDecision:
    """Security gate decision result."""

    allowed: bool
    reason: str


class SecurityAgent:
    """Security agent handling gating and compliance checks."""

    department = "security"

    def __init__(self, policy: DepartmentPolicy | None = None) -> None:
        """Initialize security agent with department-level policy."""
        self.policy = policy or DepartmentPolicy()

    def handle(self, context: AgentContext, order: WorkOrder | None = None) -> AgentResult:
        """Handle security work order such as gating or compliance checks."""
        if order is None:
            raise ValueError("SecurityAgent requires a work order.")
        if order.action == "gate_deploy":
            environment = order.payload.get("environment", "staging")
            decision = self._gate_deploy(context, environment)
            return AgentResult(
                department=self.department,
                actions=["gate_deploy"],
                artifacts=[],
                gates_run=["policy", "preauth"],
                next_steps=[],
                escalations=[] if decision.allowed else [decision.reason],
                metadata={"decision": decision},
                halted=not decision.allowed,
            )
        if order.action == "license_check":
            licenses = order.payload.get("licenses", [])
            blocked = [lic for lic in licenses if lic not in self.policy.allowed_corpus_licenses]
            allowed = not blocked
            decision = SecurityGateDecision(
                allowed=allowed,
                reason="ok" if allowed else f"blocked_licenses:{','.join(blocked)}",
            )
            return AgentResult(
                department=self.department,
                actions=["license_check"],
                artifacts=[],
                gates_run=["license"],
                next_steps=[],
                escalations=[] if allowed else [decision.reason],
                metadata={"decision": decision},
                halted=not allowed,
            )
        raise ValueError(f"Unknown security action: {order.action}")

    def _gate_deploy(self, context: AgentContext, environment: str) -> SecurityGateDecision:
        """Gate deploy actions based on policy and preauth grant."""
        policy_decision = evaluate_action(
            policy=context.policy,
            action="deploy",
            environment=environment,
        )
        if not policy_decision.allowed:
            return SecurityGateDecision(False, policy_decision.reason)
        if environment == "prod":
            grant = context.grant
            if grant is None:
                return SecurityGateDecision(False, "preauth_required")
            if not capability_allowed(grant, "auto_deploy_prod"):
                return SecurityGateDecision(False, "preauth_capability_missing")
        return SecurityGateDecision(True, "ok")


def write_threat_model(output_dir: Path, content: str) -> Path:
    """Write a basic threat model document for security artifacts."""
    security_dir = output_dir / ".autosd" / "security"
    security_dir.mkdir(parents=True, exist_ok=True)
    path = security_dir / "threat_model.md"
    path.write_text(content, encoding="utf-8")
    return path
