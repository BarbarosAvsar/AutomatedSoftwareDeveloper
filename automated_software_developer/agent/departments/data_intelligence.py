"""Data and intelligence department agent."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from automated_software_developer.agent.departments.base import AgentContext, AgentResult, WorkOrder
from automated_software_developer.agent.departments.policy import DepartmentPolicy


@dataclass(frozen=True)
class CorpusEntry:
    """External corpus entry used for pattern proposals."""

    source: str
    license: str
    summary: str
    content_hash: str


@dataclass(frozen=True)
class Proposal:
    """Proposal generated from external corpus ingestion."""

    proposal_id: str
    source: str
    recommendation: str


class DataIntelligenceAgent:
    """Data/analytics agent for telemetry insights and external learning."""

    department = "data_intelligence"

    def __init__(self, policy: DepartmentPolicy | None = None) -> None:
        """Initialize data agent with policy controls."""
        self.policy = policy or DepartmentPolicy()

    def handle(self, context: AgentContext, order: WorkOrder | None = None) -> AgentResult:
        """Handle data intelligence work order."""
        if order is None:
            raise ValueError("DataIntelligenceAgent requires a work order.")
        if order.action != "ingest_corpus":
            raise ValueError(f"Unknown data action: {order.action}")
        entries = order.payload.get("entries", [])
        analytics_dir = Path(
            order.payload.get(
                "analytics_dir",
                Path.home() / ".autosd" / "analytics",
            )
        )
        analytics_dir.mkdir(parents=True, exist_ok=True)

        blocked = [
            entry for entry in entries if entry.license not in self.policy.allowed_corpus_licenses
        ]
        if blocked:
            reasons = ",".join(sorted({entry.license for entry in blocked}))
            return AgentResult(
                department=self.department,
                actions=["ingest_corpus"],
                artifacts=[],
                gates_run=["license"],
                next_steps=[],
                escalations=[f"blocked_licenses:{reasons}"],
                metadata={"blocked": blocked},
                halted=True,
            )

        proposals: list[Proposal] = []
        for entry in entries:
            proposal_id = f"proposal-{entry.content_hash[:8]}"
            proposals.append(
                Proposal(
                    proposal_id=proposal_id,
                    source=entry.source,
                    recommendation=f"Review patterns from {entry.source}",
                )
            )

        payload = {
            "generated_at": datetime.now(tz=UTC).isoformat(),
            "proposal_count": len(proposals),
            "proposals": [proposal.__dict__ for proposal in proposals],
        }
        output_path = analytics_dir / "external_learning_proposals.json"
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        return AgentResult(
            department=self.department,
            actions=["ingest_corpus"],
            artifacts=[output_path],
            gates_run=["license"],
            next_steps=["pmo_review"],
            escalations=[],
            metadata={"proposals": proposals},
        )
