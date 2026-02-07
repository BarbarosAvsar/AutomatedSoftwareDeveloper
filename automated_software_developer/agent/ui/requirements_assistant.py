"""Deterministic requirements co-creation assistant for the UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Literal
from uuid import uuid4

Role = Literal["user", "assistant"]


@dataclass(frozen=True)
class ConversationTurn:
    """Represents a single turn in the requirements conversation."""

    role: Role
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class RequirementsDraft:
    """Structured draft requirements generated from conversation input."""

    summary: str
    goals: tuple[str, ...]
    constraints: tuple[str, ...]
    functional_requirements: tuple[str, ...]
    non_functional_requirements: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]
    risks: tuple[str, ...]
    compliance_flags: tuple[str, ...]


@dataclass
class RequirementsSession:
    """Session state for a requirements co-creation conversation."""

    session_id: str
    idea: str
    turns: list[ConversationTurn] = field(default_factory=list)
    draft: RequirementsDraft | None = None


@dataclass(frozen=True)
class RequirementsResponse:
    """Response payload returned to the UI for the next prompt."""

    session_id: str
    questions: tuple[str, ...]
    suggestions: tuple[str, ...]
    draft: RequirementsDraft


@dataclass(frozen=True)
class RequirementsValidation:
    """Validation report for requirements markdown."""

    missing_sections: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class RequirementsRefinement:
    """Refined requirements output."""

    markdown: str
    summary: str


class RequirementsAssistant:
    """Rule-based assistant for clarifying and structuring requirements."""

    def __init__(self, *, max_questions: int = 3) -> None:
        if max_questions <= 0:
            raise ValueError("max_questions must be greater than zero.")
        self._max_questions = max_questions
        self._sessions: dict[str, RequirementsSession] = {}

    def start_session(self, idea: str) -> RequirementsResponse:
        """Start a new requirements session from a user idea."""
        if not idea.strip():
            raise ValueError("idea must be non-empty.")
        session_id = uuid4().hex
        session = RequirementsSession(session_id=session_id, idea=idea)
        session.turns.append(ConversationTurn(role="user", content=idea))
        session.draft = self._build_draft(idea, session.turns)
        self._sessions[session_id] = session
        return self._build_response(session)

    def add_message(self, session_id: str, message: str) -> RequirementsResponse:
        """Add a message to an existing session and return updated draft."""
        if not session_id.strip():
            raise ValueError("session_id must be non-empty.")
        if not message.strip():
            raise ValueError("message must be non-empty.")
        session = self._get_session(session_id)
        session.turns.append(ConversationTurn(role="user", content=message))
        session.draft = self._build_draft(session.idea, session.turns)
        return self._build_response(session)

    def finalize(self, session_id: str) -> RequirementsDraft:
        """Finalize a requirements draft for the provided session."""
        session = self._get_session(session_id)
        if session.draft is None:
            raise ValueError("No draft exists for session.")
        return session.draft

    def refine_markdown(self, draft: RequirementsDraft) -> RequirementsRefinement:
        """Return a structured markdown requirements document."""
        markdown = _build_markdown_from_draft(draft)
        summary = "Structured requirements ready for review."
        return RequirementsRefinement(markdown=markdown, summary=summary)

    def validate_markdown(self, markdown: str) -> RequirementsValidation:
        """Validate markdown content for required sections."""
        if not markdown.strip():
            raise ValueError("markdown must be non-empty.")
        missing = []
        required = [
            "Problem / Goals",
            "Functional requirements",
            "Non-functional requirements",
            "Acceptance criteria",
        ]
        lowered = markdown.lower()
        for section in required:
            if section.lower() not in lowered:
                missing.append(section)
        warnings = []
        if "analytics" in lowered and "opt-in" not in lowered:
            warnings.append("Analytics should be explicitly opt-in.")
        return RequirementsValidation(missing_sections=tuple(missing), warnings=tuple(warnings))

    def _get_session(self, session_id: str) -> RequirementsSession:
        if session_id not in self._sessions:
            raise ValueError("Unknown session_id.")
        return self._sessions[session_id]

    def _build_response(self, session: RequirementsSession) -> RequirementsResponse:
        if session.draft is None:
            raise ValueError("Draft requirements not generated.")
        questions = self._build_questions(session.draft)
        suggestions = self._build_suggestions(session.draft)
        return RequirementsResponse(
            session_id=session.session_id,
            questions=questions,
            suggestions=suggestions,
            draft=session.draft,
        )

    def _build_questions(self, draft: RequirementsDraft) -> tuple[str, ...]:
        questions: list[str] = []
        if not draft.constraints:
            questions.append("Are there any constraints on stack, budget, or timeline?")
        if not draft.compliance_flags:
            questions.append("Does this need any compliance (SOC2, HIPAA, GDPR)?")
        if not draft.non_functional_requirements:
            questions.append("What performance or uptime targets should we hit?")
        if not draft.acceptance_criteria:
            questions.append("What would make this a successful first release?")
        return tuple(questions[: self._max_questions])

    def _build_suggestions(self, draft: RequirementsDraft) -> tuple[str, ...]:
        suggestions: list[str] = []
        if any("ai" in goal.lower() for goal in draft.goals):
            suggestions.append("Consider adding a human review checkpoint for AI outputs.")
        if any("real-time" in req.lower() for req in draft.functional_requirements):
            suggestions.append("Use WebSockets or SSE for live updates.")
        suggestions.append("Lock requirements before launch for auditability.")
        return tuple(suggestions)

    def _build_draft(
        self, idea: str, turns: list[ConversationTurn]
    ) -> RequirementsDraft:
        context = "\n".join(turn.content for turn in turns)
        goals = self._extract_goals(context)
        constraints = self._extract_constraints(context)
        functional = self._extract_functional(context)
        non_functional = self._extract_non_functional(context)
        acceptance = self._extract_acceptance(context)
        risks = self._extract_risks(context)
        compliance = self._extract_compliance(context)
        return RequirementsDraft(
            summary=self._build_summary(idea),
            goals=tuple(goals),
            constraints=tuple(constraints),
            functional_requirements=tuple(functional),
            non_functional_requirements=tuple(non_functional),
            acceptance_criteria=tuple(acceptance),
            risks=tuple(risks),
            compliance_flags=tuple(compliance),
        )

    def _build_summary(self, idea: str) -> str:
        return f"Project summary: {idea.strip().rstrip('.')}."

    def _extract_goals(self, context: str) -> list[str]:
        goals = [
            "Deliver a chat-first product ideation experience.",
            "Enable autonomous build launch with live progress visibility.",
        ]
        if "dashboard" in context.lower():
            goals.append("Provide a portfolio dashboard with project health indicators.")
        return goals

    def _extract_constraints(self, context: str) -> list[str]:
        constraints: list[str] = []
        if "fastapi" in context.lower():
            constraints.append("Backend must use FastAPI.")
        if "react" in context.lower():
            constraints.append("Frontend must use React and TypeScript.")
        return constraints

    def _extract_functional(self, context: str) -> list[str]:
        requirements = [
            "Chat-based ideation with clarification questions.",
            "Requirements editor with approval workflow.",
            "One-click autonomous build launch.",
            "Real-time agent activity stream.",
        ]
        if "deployment" in context.lower():
            requirements.append("Deployment history with rollback controls.")
        return requirements

    def _extract_non_functional(self, context: str) -> list[str]:
        requirements: list[str] = []
        if "real-time" in context.lower():
            requirements.append("Real-time updates delivered in under two seconds.")
        if "safe" in context.lower():
            requirements.append("Safety-by-default gating with audit trails.")
        return requirements

    def _extract_acceptance(self, context: str) -> list[str]:
        criteria = [
            "User can launch an autonomous build with no follow-up prompts.",
            "All actions are visible with timestamps and reasons.",
        ]
        if "monitor" in context.lower():
            criteria.append("Dashboards show deployments, incidents, and metrics live.")
        return criteria

    def _extract_risks(self, context: str) -> list[str]:
        risks = [
            "Ambiguous requirements could lead to incorrect automation scope.",
            "Autonomy requires clear preauth policy validation.",
        ]
        if "ai" in context.lower():
            risks.append("AI output may need guardrails for sensitive actions.")
        return risks

    def _extract_compliance(self, context: str) -> list[str]:
        flags: list[str] = []
        if "gdpr" in context.lower():
            flags.append("GDPR")
        if "hipaa" in context.lower():
            flags.append("HIPAA")
        if "soc2" in context.lower():
            flags.append("SOC2")
        return flags


def parse_requirements_upload(filename: str, content: bytes) -> str:
    """Parse requirements upload content from md/txt/pdf."""
    if not filename.strip():
        raise ValueError("filename must be non-empty.")
    if not content:
        raise ValueError("content must be non-empty.")
    suffix = Path(filename).suffix.lower()
    if suffix in {".md", ".txt"}:
        return content.decode("utf-8", errors="replace").strip()
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover - dependency missing
            raise ValueError("PDF parsing dependency is unavailable.") from exc
        reader = PdfReader(BytesIO(content))
        text_parts = []
        for page in reader.pages:
            text_parts.append(page.extract_text() or "")
        text = "\n".join(text_parts).strip()
        if not text:
            raise ValueError("PDF contained no extractable text.")
        return text
    raise ValueError("Unsupported file type.")


def _build_markdown_from_draft(draft: RequirementsDraft) -> str:
    lines = [
        "# Requirements",
        "",
        "## Problem / Goals",
        *(f"- {goal}" for goal in draft.goals),
        "",
        "## Users / Personas (optional)",
        "- TBD",
        "",
        "## Functional requirements",
        *(f"- {req}" for req in draft.functional_requirements),
        "",
        "## Non-functional requirements",
        *(f"- {req}" for req in draft.non_functional_requirements),
        "",
        "## Platforms/targets",
        "- Web",
        "",
        "## Deployment targets & environments",
        "- Dev, Staging, Production",
        "",
        "## Analytics requirement (optional)",
        "- Opt-in only if explicitly requested.",
        "",
        "## Legal/licensing/monetization flags (optional)",
        "- TBD",
        "",
        "## Constraints",
        *(f"- {item}" for item in draft.constraints),
        "",
        "## Acceptance criteria / Definition of Done additions",
        *(f"- {item}" for item in draft.acceptance_criteria),
        "",
        "## Risks",
        *(f"- {item}" for item in draft.risks),
    ]
    return "\n".join(lines).strip()
