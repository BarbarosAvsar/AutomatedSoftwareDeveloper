"""Support and customer operations department agent."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime

from automated_software_developer.agent.departments.base import AgentContext, AgentResult, WorkOrder


@dataclass(frozen=True)
class SupportTicket:
    """Structured support ticket entry."""

    ticket_id: str
    project_id: str
    severity: str
    category: str
    summary: str
    routed_department: str
    created_at: str


class SupportOpsAgent:
    """Support agent for intake, triage, and routing."""

    department = "support_ops"

    def handle(self, context: AgentContext, order: WorkOrder | None = None) -> AgentResult:
        """Handle support intake work order."""
        if order is None or order.action != "triage":
            raise ValueError("SupportOpsAgent expects triage work order.")
        payload = order.payload
        summary = payload.get("summary", "")
        severity = payload.get("severity", "low")
        category = payload.get("category", "general")
        routed = _route_category(category)

        ticket_id = payload.get("ticket_id") or (
            f"ticket-{datetime.now(tz=UTC).strftime('%Y%m%d%H%M%S')}"
        )
        created_at = datetime.now(tz=UTC).isoformat()
        ticket = SupportTicket(
            ticket_id=ticket_id,
            project_id=context.project_id,
            severity=severity,
            category=category,
            summary=summary,
            routed_department=routed,
            created_at=created_at,
        )

        support_dir = context.project_dir / ".autosd" / "support"
        support_dir.mkdir(parents=True, exist_ok=True)
        ticket_path = support_dir / f"{ticket_id}.json"
        ticket_path.write_text(json.dumps(ticket.__dict__, indent=2), encoding="utf-8")

        return AgentResult(
            department=self.department,
            actions=["triage"],
            artifacts=[ticket_path],
            gates_run=["triage"],
            next_steps=[f"route:{routed}"],
            escalations=[],
            metadata={"ticket": ticket},
        )


def _route_category(category: str) -> str:
    """Route support category to department."""
    normalized = category.lower()
    if normalized in {"security", "compliance"}:
        return "security"
    if normalized in {"outage", "deploy", "availability"}:
        return "operations"
    return "engineering"
