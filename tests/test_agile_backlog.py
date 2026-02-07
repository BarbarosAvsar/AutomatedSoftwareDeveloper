import json

from automated_software_developer.agent.agile.backlog import AgileBacklog, build_backlog
from automated_software_developer.agent.models import (
    AssumptionItem,
    RefinedRequirements,
    RefinedStory,
)


def _sample_refined() -> RefinedRequirements:
    story = RefinedStory(
        story_id="S1",
        title="Account creation",
        story="As a user I want to create an account so that I can sign in.",
        acceptance_criteria=[
            "Account form exists",
            "Email validation works",
            "Password validation works",
            "Account is persisted",
            "Confirmation is sent",
        ],
        nfr_tags=["security"],
        dependencies=[],
        verification_commands=[],
    )
    return RefinedRequirements(
        project_name="Demo",
        product_brief="Demo product",
        personas=["user"],
        stories=[story],
        nfrs={"security": ["passwords are hashed"]},
        ambiguities=[],
        contradictions=[],
        missing_constraints=[],
        edge_cases=[],
        external_dependencies=[],
        assumptions=[
            AssumptionItem(
                assumption="No external auth provider",
                testable_criterion="Auth handled locally",
            )
        ],
        stack_rationale="Python",
        global_verification_commands=[],
    )


def test_build_backlog_splits_large_story() -> None:
    refined = _sample_refined()
    backlog = build_backlog(refined)
    assert backlog.project_name == "Demo"
    assert len(backlog.stories) == 2
    assert backlog.stories[0].estimate_points >= 1


def test_backlog_serialization_roundtrip() -> None:
    refined = _sample_refined()
    backlog = build_backlog(refined)
    payload = backlog.to_dict()
    restored = AgileBacklog.from_dict(json.loads(json.dumps(payload)))
    assert restored.project_name == backlog.project_name
    assert restored.stories[0].story_id == backlog.stories[0].story_id
