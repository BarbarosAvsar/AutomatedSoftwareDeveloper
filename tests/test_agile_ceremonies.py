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


def _refined_story() -> RefinedRequirements:
    story = RefinedStory(
        story_id="S1",
        title="Export report",
        story="As a user I want to export a report so that I can share results.",
        acceptance_criteria=["Export succeeds", "File saved"],
        nfr_tags=[],
        dependencies=[],
        verification_commands=[],
    )
    return RefinedRequirements(
        project_name="CeremonyDemo",
        product_brief="Ceremony demo",
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
                assumption="No external storage",
                testable_criterion="Local writes only",
            )
        ],
        stack_rationale="Python",
        global_verification_commands=[],
    )


def test_review_and_retrospective(tmp_path: Path) -> None:
    backlog = build_backlog(_refined_story())
    metrics = MetricsStore(path=tmp_path / "metrics.json")
    metrics.load()
    plan = run_sprint_planning(backlog, metrics)
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
    review = run_sprint_review(plan, backlog=backlog, dod_result=dod_result)
    assert review.completed_story_ids
    retro = run_retrospective(plan, metrics)
    assert "Sprint Retrospective" in retro
