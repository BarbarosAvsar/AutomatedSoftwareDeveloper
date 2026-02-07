"""Autonomous requirements refinement into canonical Agile-ready specification."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from automated_software_developer.agent.models import (
    AssumptionItem,
    PromptTemplate,
    RefinedRequirements,
    RefinedStory,
)
from automated_software_developer.agent.prompts import (
    build_requirements_refinement_system_prompt,
    build_requirements_refinement_user_prompt,
)
from automated_software_developer.agent.providers.base import LLMProvider

NFR_KEYWORDS: dict[str, tuple[str, ...]] = {
    "security": ("auth", "authentication", "authorization", "token", "security", "encrypt"),
    "privacy": ("privacy", "pii", "personal data", "gdpr", "sensitive"),
    "performance": ("performance", "latency", "fast", "throughput", "scale", "scalable"),
    "reliability": ("reliability", "availability", "uptime", "retry", "fault"),
    "observability": ("logging", "metrics", "tracing", "monitoring", "observability"),
    "ux_accessibility": ("ui", "ux", "accessibility", "a11y", "frontend", "mobile"),
    "compliance": ("hipaa", "pci", "soc 2", "sox", "compliance"),
}

AMBIGUOUS_TERMS = ("etc", "and so on", "user-friendly", "fast", "as needed", "quickly")

KNOWN_DEPENDENCIES = (
    "github",
    "aws",
    "gcp",
    "azure",
    "docker",
    "kubernetes",
    "postgres",
    "mysql",
    "mongodb",
    "redis",
    "fastapi",
    "django",
    "flask",
    "react",
    "node",
)


@dataclass(frozen=True)
class HeuristicAnalysis:
    """Rule-based analysis used to harden requirement refinement."""

    nfr_hints: dict[str, list[str]]
    ambiguity_signals: list[str]
    contradiction_signals: list[str]
    missing_constraints: list[str]
    edge_cases: list[str]
    external_dependencies: list[str]
    assumptions: list[AssumptionItem]

    def to_prompt_notes(self) -> str:
        """Render compact heuristic notes for model prompting."""
        lines: list[str] = ["NFR hints:"]
        for category, hints in sorted(self.nfr_hints.items()):
            if hints:
                lines.append(f"- {category}: {', '.join(hints)}")
        lines.append("Ambiguities:")
        lines.extend(f"- {item}" for item in self.ambiguity_signals or ["- none identified"])
        lines.append("Potential contradictions:")
        lines.extend(f"- {item}" for item in self.contradiction_signals or ["- none identified"])
        lines.append("Likely missing constraints:")
        lines.extend(f"- {item}" for item in self.missing_constraints or ["- none identified"])
        lines.append("Edge-case hints:")
        lines.extend(f"- {item}" for item in self.edge_cases or ["- none identified"])
        lines.append("Potential external dependencies:")
        lines.extend(f"- {item}" for item in self.external_dependencies or ["- none identified"])
        lines.append("Assumptions to convert into testable criteria:")
        for item in self.assumptions:
            lines.append(f"- {item.assumption} -> {item.testable_criterion}")
        return "\n".join(lines)


class RequirementsRefiner:
    """Creates canonical refined requirements from raw input text."""

    def __init__(self, provider: LLMProvider) -> None:
        """Initialize refiner with model provider."""
        self.provider = provider

    def refine(
        self,
        requirements: str,
        repo_guidelines: str | None,
        template: PromptTemplate,
        *,
        seed: int | None = None,
    ) -> RefinedRequirements:
        """Generate a refined requirements specification with autonomous assumptions."""
        if not requirements.strip():
            raise ValueError("requirements must be non-empty for refinement.")
        if not template.template_id.strip():
            raise ValueError("template.template_id must be non-empty.")
        heuristics = self._analyze(requirements)
        response = self.provider.generate_json(
            system_prompt=build_requirements_refinement_system_prompt(template),
            user_prompt=build_requirements_refinement_user_prompt(
                requirements=requirements,
                repo_guidelines=repo_guidelines,
                heuristic_notes=heuristics.to_prompt_notes(),
            ),
            seed=seed,
        )
        normalized = self._normalize_raw_response(response, heuristics)
        refined = RefinedRequirements.from_dict(normalized)
        return self._merge_heuristics(refined, heuristics)

    def _analyze(self, requirements: str) -> HeuristicAnalysis:
        """Run deterministic heuristic analysis over requirement text."""
        lowered = requirements.lower()
        nfr_hints: dict[str, list[str]] = {key: [] for key in NFR_KEYWORDS}
        for category, keywords in NFR_KEYWORDS.items():
            for keyword in keywords:
                if keyword in lowered:
                    nfr_hints[category].append(f"Requirement text references '{keyword}'.")
                    break

        ambiguity_signals = [
            f"Ambiguous term '{term}' detected."
            for term in AMBIGUOUS_TERMS
            if term in lowered
        ]
        contradiction_signals: list[str] = []
        if "must" in lowered and "must not" in lowered:
            contradiction_signals.append(
                "The spec contains both 'must' and 'must not'; verify rule intent."
            )
        if "without authentication" in lowered and "auth" in lowered:
            contradiction_signals.append(
                "Authentication appears both required and bypassed in separate statements."
            )

        missing_constraints: list[str] = []
        if "test" not in lowered:
            missing_constraints.append("No explicit testing strategy stated.")
        if "error" not in lowered and "exception" not in lowered:
            missing_constraints.append("No explicit error-handling behavior stated.")
        if "performance" not in lowered and "latency" not in lowered:
            missing_constraints.append("No explicit performance budget stated.")

        edge_cases: list[str] = []
        if any(token in lowered for token in ("auth", "login", "token")):
            edge_cases.extend(
                [
                    "Expired or revoked credentials.",
                    "Repeated failed login attempts and lockout handling.",
                ]
            )
        if any(token in lowered for token in ("api", "service", "endpoint")):
            edge_cases.extend(
                [
                    "Malformed input payloads.",
                    "Idempotency and retry safety for repeated requests.",
                ]
            )
        if any(token in lowered for token in ("ui", "frontend", "web", "mobile")):
            edge_cases.extend(
                [
                    "Keyboard-only navigation and screen-reader compatibility.",
                    "Small-screen behavior under reduced viewport width.",
                ]
            )

        external_dependencies = [name for name in KNOWN_DEPENDENCIES if name in lowered]
        assumptions: list[AssumptionItem] = []
        for signal in ambiguity_signals:
            term = signal.split("'")[1] if "'" in signal else "ambiguous requirement"
            assumptions.append(
                AssumptionItem(
                    assumption=f"Interpret '{term}' as measurable behavior validated by tests.",
                    testable_criterion=(
                        f"Given '{term}' appears in requirements, when implementation is complete, "
                        "then at least one executable test verifies the interpreted behavior."
                    ),
                )
            )
        if not assumptions:
            assumptions.append(
                AssumptionItem(
                    assumption=(
                        "Default to secure, maintainable behavior when details are unspecified."
                    ),
                    testable_criterion=(
                        "Given an unspecified behavior, when software is generated, then tests and "
                        "documentation describe the chosen secure default."
                    ),
                )
            )
        return HeuristicAnalysis(
            nfr_hints=nfr_hints,
            ambiguity_signals=ambiguity_signals,
            contradiction_signals=contradiction_signals,
            missing_constraints=missing_constraints,
            edge_cases=edge_cases,
            external_dependencies=external_dependencies,
            assumptions=assumptions,
        )

    def _normalize_raw_response(
        self,
        response: dict[str, Any],
        heuristics: HeuristicAnalysis,
    ) -> dict[str, Any]:
        """Normalize partial model output into a valid refinement schema shape."""
        normalized: dict[str, Any] = dict(response)
        stories = normalized.get("stories")
        if not isinstance(stories, list):
            stories = []
        normalized_stories: list[dict[str, Any]] = []
        for index, item in enumerate(stories):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", f"Story {index + 1}")).strip() or f"Story {index + 1}"
            story_text = str(item.get("story", title)).strip()
            if not story_text.lower().startswith("as a"):
                story_text = (
                    f"As a user, I want {story_text.lower()} so that "
                    "the product requirements are satisfied."
                )
            criteria_raw = item.get("acceptance_criteria")
            criteria: list[str]
            if isinstance(criteria_raw, list):
                criteria = [
                    self._ensure_given_when_then(str(value))
                    for value in criteria_raw
                    if value
                ]
            else:
                criteria = []
            if not criteria:
                criteria = [
                    self._ensure_given_when_then(
                        f"{title} functionality behaves as required under normal "
                        "and edge conditions."
                    )
                ]
            normalized_stories.append(
                {
                    "id": str(item.get("id", f"story-{index + 1}")).strip() or f"story-{index + 1}",
                    "title": title,
                    "story": story_text,
                    "acceptance_criteria": criteria,
                    "nfr_tags": item.get("nfr_tags", []),
                    "dependencies": item.get("dependencies", []),
                    "verification_commands": item.get("verification_commands", []),
                }
            )
        if not normalized_stories:
            normalized_stories = [
                {
                    "id": "story-1",
                    "title": "Implement baseline requirements",
                    "story": (
                        "As a user, I want the requested software implemented so that I can use it "
                        "for its intended purpose."
                    ),
                    "acceptance_criteria": [
                        self._ensure_given_when_then(
                            "Core requirements are implemented with automated verification."
                        )
                    ],
                    "nfr_tags": ["security", "reliability"],
                    "dependencies": [],
                    "verification_commands": [],
                }
            ]
        normalized["stories"] = normalized_stories

        assumptions = normalized.get("assumptions")
        normalized_assumptions: list[dict[str, str]] = []
        if isinstance(assumptions, list):
            for item in assumptions:
                if isinstance(item, dict):
                    assumption = str(item.get("assumption", "")).strip()
                    criterion = str(item.get("testable_criterion", "")).strip()
                    if not assumption:
                        continue
                    normalized_assumptions.append(
                        {
                            "assumption": assumption,
                            "testable_criterion": (
                                self._ensure_given_when_then(criterion)
                                if criterion
                                else self._ensure_given_when_then(
                                    f"Assumption '{assumption}' is validated."
                                )
                            ),
                        }
                    )
                elif isinstance(item, str) and item.strip():
                    normalized_assumptions.append(
                        {
                            "assumption": item.strip(),
                            "testable_criterion": self._ensure_given_when_then(
                                f"Assumption '{item.strip()}' is validated."
                            ),
                        }
                    )
        if not normalized_assumptions:
            normalized_assumptions = [
                {
                    "assumption": item.assumption,
                    "testable_criterion": item.testable_criterion,
                }
                for item in heuristics.assumptions
            ]
        normalized["assumptions"] = normalized_assumptions

        nfrs_raw = normalized.get("nfrs")
        nfrs = nfrs_raw if isinstance(nfrs_raw, dict) else {}
        for category in NFR_KEYWORDS:
            if category not in nfrs or not isinstance(nfrs[category], list):
                nfrs[category] = []
        normalized["nfrs"] = nfrs

        normalized.setdefault(
            "global_verification_commands",
            [
                "python -m ruff check .",
                "python -m mypy automated_software_developer",
                "python -m pytest",
            ],
        )
        normalized.setdefault("ambiguities", [])
        normalized.setdefault("contradictions", [])
        normalized.setdefault("missing_constraints", [])
        normalized.setdefault("edge_cases", [])
        normalized.setdefault("external_dependencies", [])
        normalized.setdefault(
            "project_name",
            "Generated Project",
        )
        normalized.setdefault(
            "product_brief",
            "Autonomously generated software project from refined requirements.",
        )
        normalized.setdefault("personas", ["Primary user"])
        normalized.setdefault(
            "stack_rationale",
            "Selected stack balances implementation speed, maintainability, and testability.",
        )
        return normalized

    def _merge_heuristics(
        self,
        refined: RefinedRequirements,
        heuristics: HeuristicAnalysis,
    ) -> RefinedRequirements:
        """Merge model output and heuristic findings into final refined requirements."""
        stories = [self._normalize_story(story) for story in refined.stories]
        personas = refined.personas or ["Primary user"]

        merged_nfrs: dict[str, list[str]] = {}
        for category in sorted(set(refined.nfrs) | set(heuristics.nfr_hints)):
            merged_nfrs[category] = _dedupe(
                [*refined.nfrs.get(category, []), *heuristics.nfr_hints.get(category, [])]
            )

        assumptions = _dedupe_assumptions([*refined.assumptions, *heuristics.assumptions])
        return replace(
            refined,
            personas=personas,
            stories=stories,
            nfrs=merged_nfrs,
            ambiguities=_dedupe([*refined.ambiguities, *heuristics.ambiguity_signals]),
            contradictions=_dedupe([*refined.contradictions, *heuristics.contradiction_signals]),
            missing_constraints=_dedupe(
                [*refined.missing_constraints, *heuristics.missing_constraints]
            ),
            edge_cases=_dedupe([*refined.edge_cases, *heuristics.edge_cases]),
            external_dependencies=_dedupe(
                [*refined.external_dependencies, *heuristics.external_dependencies]
            ),
            assumptions=assumptions,
        )

    def _normalize_story(self, story: RefinedStory) -> RefinedStory:
        """Normalize story text and acceptance criteria formatting."""
        criteria = [self._ensure_given_when_then(item) for item in story.acceptance_criteria]
        if not criteria:
            criteria = [self._ensure_given_when_then(f"{story.title} functions correctly.")]
        story_text = story.story
        if not story_text.lower().startswith("as a"):
            story_text = (
                f"As a user, I want {story_text.lower()} so that the product requirements are met."
            )
        return replace(story, story=story_text, acceptance_criteria=_dedupe(criteria))

    def _ensure_given_when_then(self, text: str) -> str:
        """Ensure acceptance criterion is in Given/When/Then style."""
        cleaned = text.strip()
        lowered = cleaned.lower()
        if "given" in lowered and "when" in lowered and "then" in lowered:
            return cleaned
        return (
            f"Given the feature is implemented, when validation executes for '{cleaned}', "
            "then expected behavior is confirmed."
        )


def _dedupe(items: list[str]) -> list[str]:
    """Remove duplicates while preserving item order."""
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _dedupe_assumptions(items: list[AssumptionItem]) -> list[AssumptionItem]:
    """Remove duplicate assumption pairs while preserving order."""
    seen: set[tuple[str, str]] = set()
    ordered: list[AssumptionItem] = []
    for item in items:
        key = (item.assumption.strip(), item.testable_criterion.strip())
        if not all(key) or key in seen:
            continue
        seen.add(key)
        ordered.append(item)
    return ordered
