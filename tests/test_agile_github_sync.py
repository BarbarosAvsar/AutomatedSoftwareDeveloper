import json
from pathlib import Path

from automated_software_developer.agent.agile.backlog import build_backlog
from automated_software_developer.agent.agile.github_sync import (
    GitHubProjectConfig,
    GitHubProjectSync,
)
from automated_software_developer.agent.agile.metrics import MetricsStore
from automated_software_developer.agent.agile.sprint_engine import plan_sprint
from automated_software_developer.agent.models import (
    AssumptionItem,
    RefinedRequirements,
    RefinedStory,
)


def _refined() -> RefinedRequirements:
    story = RefinedStory(
        story_id="S1",
        title="Sync story",
        story="As a user I want sync so that project updates.",
        acceptance_criteria=["Criteria"],
        nfr_tags=[],
        dependencies=[],
        verification_commands=[],
    )
    return RefinedRequirements(
        project_name="SyncDemo",
        product_brief="Sync demo",
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
                assumption="No external API",
                testable_criterion="Local only",
            )
        ],
        stack_rationale="Python",
        global_verification_commands=[],
    )


def test_github_sync_dry_run(tmp_path: Path) -> None:
    backlog = build_backlog(_refined())
    metrics_store = MetricsStore(path=tmp_path / "metrics.json")
    metrics_store.load()
    sprint = plan_sprint(backlog, metrics_store.snapshot())
    log_path = tmp_path / "github_sync.json"
    sync = GitHubProjectSync(
        GitHubProjectConfig(repo="org/repo", project_number=1, dry_run=True),
        log_path=log_path,
    )
    result = sync.sync_backlog(backlog)
    assert result["status"] == "dry_run"
    payload = json.loads(log_path.read_text(encoding="utf-8"))
    assert payload["action"] in {"backlog", "sprint"}
    _ = sync.sync_sprint(sprint)
