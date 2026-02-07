"""Department agent interfaces and shared dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from automated_software_developer.agent.audit import AuditLogger
from automated_software_developer.agent.policy.engine import EffectivePolicy
from automated_software_developer.agent.preauth.grants import PreauthGrant


@dataclass(frozen=True)
class AgentContext:
    """Context provided to department agents for handling work."""

    project_id: str
    project_dir: Path
    policy: EffectivePolicy
    grant: PreauthGrant | None
    audit_logger: AuditLogger
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentResult:
    """Result returned by department agents."""

    department: str
    actions: list[str]
    artifacts: list[Path]
    gates_run: list[str]
    next_steps: list[str]
    escalations: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)
    halted: bool = False


@dataclass(frozen=True)
class WorkOrder:
    """Structured work order issued by Program Management."""

    department: str
    action: str
    payload: dict[str, Any]


class DepartmentAgent(Protocol):
    """Protocol for department agents."""

    department: str

    def handle(self, context: AgentContext, order: WorkOrder | None = None) -> AgentResult:
        """Handle one work order or context-driven action."""
        raise NotImplementedError
