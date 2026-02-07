from automated_software_developer.agent.agile.backlog import build_backlog
from automated_software_developer.agent.agile.metrics import MetricsStore
from automated_software_developer.agent.agile.sprint_engine import SprintConfig, plan_sprint
from automated_software_developer.agent.models import (
    AssumptionItem,
    RefinedRequirements,
    RefinedStory,
)


def _refined_with_story(story_id: str) -> RefinedRequirements:
    story = RefinedStory(
        story_id=story_id,
        title=f"Story {story_id}",
        story="As a user I want a feature so that value is delivered.",
        acceptance_criteria=["Criterion A", "Criterion B"],
        nfr_tags=[],
        dependencies=[],
        verification_commands=[],
    )
    return RefinedRequirements(
        project_name="SprintDemo",
        product_brief="Sprint demo",
        personas=["user"],
        stories=[story],
        nfrs={},
        ambiguities=[],
        contradictions=[],
        missing_constraints=[],
        edge_cases=[],
        external_dependencies=[],
        assumptions=[
            AssumptionItem(
                assumption="No external APIs",
                testable_criterion="Local only",
            )
        ],
        stack_rationale="Python",
        global_verification_commands=[],
    )


def test_plan_sprint_uses_velocity_history(tmp_path) -> None:
    backlog = build_backlog(_refined_with_story("S1"))
    store = MetricsStore(path=tmp_path / "metrics.json")
    store.load()
    store.record_sprint(velocity=8, cycle_time=2.0, lead_time=3.0)
    config = SprintConfig(length_days=7, velocity_lookback=1, default_capacity_points=5)
    plan = plan_sprint(backlog, store.snapshot(), config)
    assert plan.capacity_points == 8
    assert plan.stories
