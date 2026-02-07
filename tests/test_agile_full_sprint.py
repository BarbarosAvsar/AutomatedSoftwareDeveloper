from pathlib import Path

from automated_software_developer.agent.agile.backlog import build_backlog
from automated_software_developer.agent.agile.ceremonies import (
    run_retrospective,
    run_sprint_planning,
    run_sprint_review,
)
from automated_software_developer.agent.agile.dod import DoDChecklist, evaluate_definition_of_done
from automated_software_developer.agent.agile.metrics import MetricsStore
from automated_software_developer.agent.models import (
    AssumptionItem,
    RefinedRequirements,
    RefinedStory,
)


def _refined() -> RefinedRequirements:
    story = RefinedStory(
        story_id="S1",
        title="End-to-end",
        story="As a user I want a flow so that I can complete tasks.",
        acceptance_criteria=["Flow works", "Outputs stored"],
        nfr_tags=[],
        dependencies=[],
        verification_commands=[],
    )
    return RefinedRequirements(
        project_name="FullSprint",
        product_brief="Full sprint demo",
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
                assumption="Single user",
                testable_criterion="No concurrency",
            )
        ],
        stack_rationale="Python",
        global_verification_commands=[],
    )


def test_full_sprint_simulation(tmp_path: Path) -> None:
    backlog = build_backlog(_refined())
    metrics_store = MetricsStore(path=tmp_path / "metrics.json")
    metrics_store.load()
    sprint = run_sprint_planning(backlog, metrics_store)
    dod = DoDChecklist(
        compile_passed=True,
        tests_passed=True,
        lint_passed=True,
        type_check_passed=True,
        security_scan_passed=True,
        docs_updated=True,
        deployment_successful=True,
    )
    dod_result = evaluate_definition_of_done(dod)
    review = run_sprint_review(sprint, backlog=backlog, dod_result=dod_result)
    assert review.completed_story_ids
    retro = run_retrospective(sprint, metrics_store)
    assert "Improvements" in retro
