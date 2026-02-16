"""CLI command registrations."""

from __future__ import annotations

# mypy: ignore-errors
# ruff: noqa: B008,F403,F405,I001
from automated_software_developer.commands.common import *

@backlog_app.command("refine")
def backlog_refine(
    requirements_file: Annotated[
        Path | None,
        typer.Option(help="Path to markdown/text requirements specification."),
    ] = None,
    requirements_text: Annotated[
        str | None,
        typer.Option(help="Inline requirements specification string."),
    ] = None,
    output_dir: Annotated[
        Path,
        typer.Option(help="Output directory for backlog artifacts."),
    ] = Path("generated_project"),
    provider: Annotated[
        str,
        typer.Option(help="Model provider to use: openai, resilient, or mock."),
    ] = "openai",
    model: Annotated[
        str,
        typer.Option(help="Model name when using OpenAI provider."),
    ] = "gpt-5.3-codex",
    mock_responses_file: Annotated[
        Path | None,
        typer.Option(help="JSON file of queued responses when provider=mock."),
    ] = None,
) -> None:
    """Refine requirements into a Scrum backlog."""
    requirements = _load_requirements(requirements_file, requirements_text)
    resolved_provider = _create_provider(provider, model, mock_responses_file)
    agent = SoftwareDevelopmentAgent(provider=resolved_provider)
    refined = agent.refine_requirements(requirements=requirements, output_dir=output_dir)
    backlog = build_backlog(refined)
    backlog_path = output_dir / ".autosd" / "backlog.json"
    backlog_path.parent.mkdir(parents=True, exist_ok=True)
    backlog_path.write_text(json.dumps(backlog.to_dict(), indent=2), encoding="utf-8")
    console.print(f"Backlog created at {backlog_path}")


@sprint_app.command("plan")
def sprint_plan(
    backlog_path: Annotated[
        Path,
        typer.Option(help="Path to backlog.json file."),
    ] = Path("generated_project/.autosd/backlog.json"),
    metrics_path: Annotated[
        Path,
        typer.Option(help="Path to metrics.json file."),
    ] = Path("generated_project/.autosd/metrics.json"),
    sprint_length_days: Annotated[
        int,
        typer.Option(help="Sprint length in days."),
    ] = 14,
    velocity_lookback: Annotated[
        int,
        typer.Option(help="Velocity lookback count."),
    ] = 3,
    default_capacity: Annotated[
        int,
        typer.Option(help="Default capacity points."),
    ] = 10,
    github_repo: Annotated[
        str | None,
        typer.Option(help="GitHub repository (owner/name) for project sync."),
    ] = None,
    github_project_number: Annotated[
        int | None,
        typer.Option(help="GitHub Project number for project sync."),
    ] = None,
) -> None:
    """Plan a sprint based on backlog and metrics."""
    backlog_payload = json.loads(backlog_path.read_text(encoding="utf-8"))
    backlog = AgileBacklog.from_dict(backlog_payload)
    metrics_store = MetricsStore(path=metrics_path)
    config = SprintConfig(
        length_days=_ensure_positive(sprint_length_days, "sprint_length_days"),
        velocity_lookback=_ensure_positive(velocity_lookback, "velocity_lookback"),
        default_capacity_points=_ensure_positive(default_capacity, "default_capacity"),
    )
    plan = run_sprint_planning(backlog, metrics_store, config=config)
    sprint_dir = backlog_path.parent / "sprints" / plan.sprint_id
    sprint_dir.mkdir(parents=True, exist_ok=True)
    sprint_plan_path = sprint_dir / "sprint_plan.json"
    sprint_plan_path.write_text(json.dumps(plan.to_dict(), indent=2), encoding="utf-8")
    console.print(f"Sprint planned: {plan.sprint_id}")
    if github_repo and github_project_number:
        sync = GitHubProjectSync(
            GitHubProjectConfig(
                repo=github_repo,
                project_number=github_project_number,
                dry_run=True,
            )
        )
        sync.sync_backlog(backlog)
        sync.sync_sprint(plan)
        console.print("GitHub sync completed (dry run).")


@sprint_app.command("start")
def sprint_start(
    sprint_plan_path: Annotated[
        Path,
        typer.Option(help="Path to sprint plan JSON."),
    ] = Path("generated_project/.autosd/sprints/latest/sprint_plan.json"),
) -> None:
    """Start a sprint and freeze scope."""
    plan_payload = json.loads(sprint_plan_path.read_text(encoding="utf-8"))
    plan = SprintPlan(
        sprint_id=plan_payload["sprint_id"],
        goal=plan_payload["goal"],
        start_date=plan_payload["start_date"],
        end_date=plan_payload["end_date"],
        capacity_points=plan_payload["capacity_points"],
        stories=[BacklogStoryItem.from_dict(story) for story in plan_payload.get("stories", [])],
        status="active",
        frozen=plan_payload.get("frozen", False),
        metadata=plan_payload.get("metadata", {}),
    )
    frozen = freeze_sprint(plan, allow_override=False)
    sprint_plan_path.write_text(json.dumps(frozen.to_dict(), indent=2), encoding="utf-8")
    console.print(f"Sprint started and frozen: {frozen.sprint_id}")


@sprint_app.command("review")
def sprint_review(
    backlog_path: Annotated[
        Path,
        typer.Option(help="Path to backlog.json file."),
    ] = Path("generated_project/.autosd/backlog.json"),
    sprint_plan_path: Annotated[
        Path,
        typer.Option(help="Path to sprint plan JSON."),
    ] = Path("generated_project/.autosd/sprints/latest/sprint_plan.json"),
    compile_passed: Annotated[bool, typer.Option(help="Compilation succeeded.")] = True,
    tests_passed: Annotated[bool, typer.Option(help="Tests passed.")] = True,
    lint_passed: Annotated[bool, typer.Option(help="Lint checks passed.")] = True,
    type_check_passed: Annotated[bool, typer.Option(help="Type checks passed.")] = True,
    security_scan_passed: Annotated[bool, typer.Option(help="Security scan passed.")] = True,
    docs_updated: Annotated[bool, typer.Option(help="Documentation updated.")] = True,
    deployment_successful: Annotated[bool, typer.Option(help="Deployment successful.")] = True,
) -> None:
    """Run a sprint review and DoD evaluation."""
    backlog = AgileBacklog.from_dict(json.loads(backlog_path.read_text(encoding="utf-8")))
    plan_payload = json.loads(sprint_plan_path.read_text(encoding="utf-8"))
    plan = SprintPlan(
        sprint_id=plan_payload["sprint_id"],
        goal=plan_payload["goal"],
        start_date=plan_payload["start_date"],
        end_date=plan_payload["end_date"],
        capacity_points=plan_payload["capacity_points"],
        stories=[BacklogStoryItem.from_dict(story) for story in plan_payload.get("stories", [])],
        status=plan_payload.get("status", "planned"),
        frozen=plan_payload.get("frozen", False),
        metadata=plan_payload.get("metadata", {}),
    )
    dod = DoDChecklist(
        compile_passed=compile_passed,
        tests_passed=tests_passed,
        lint_passed=lint_passed,
        type_check_passed=type_check_passed,
        security_scan_passed=security_scan_passed,
        docs_updated=docs_updated,
        deployment_successful=deployment_successful,
    )
    dod_result = evaluate_definition_of_done(dod)
    review = run_sprint_review(plan, backlog=backlog, dod_result=dod_result)
    review_path = sprint_plan_path.parent / "sprint_review.json"
    review_path.write_text(json.dumps(review.__dict__, indent=2), encoding="utf-8")
    console.print(f"Sprint review completed: {review_path}")


@sprint_app.command("retro")
def sprint_retro(
    sprint_plan_path: Annotated[
        Path,
        typer.Option(help="Path to sprint plan JSON."),
    ] = Path("generated_project/.autosd/sprints/latest/sprint_plan.json"),
    metrics_path: Annotated[
        Path,
        typer.Option(help="Path to metrics.json file."),
    ] = Path("generated_project/.autosd/metrics.json"),
) -> None:
    """Run a sprint retrospective."""
    plan_payload = json.loads(sprint_plan_path.read_text(encoding="utf-8"))
    plan = SprintPlan(
        sprint_id=plan_payload["sprint_id"],
        goal=plan_payload["goal"],
        start_date=plan_payload["start_date"],
        end_date=plan_payload["end_date"],
        capacity_points=plan_payload["capacity_points"],
        stories=[BacklogStoryItem.from_dict(story) for story in plan_payload.get("stories", [])],
        status=plan_payload.get("status", "planned"),
        frozen=plan_payload.get("frozen", False),
        metadata=plan_payload.get("metadata", {}),
    )
    metrics_store = MetricsStore(path=metrics_path)
    content = run_retrospective(plan, metrics_store)
    output_dir = sprint_plan_path.parents[1] / "retrospectives"
    path = write_retrospective(content, output_dir=output_dir, sprint_id=plan.sprint_id)
    console.print(f"Retrospective saved: {path}")


@sprint_app.command("metrics")
def sprint_metrics(
    metrics_path: Annotated[
        Path,
        typer.Option(help="Path to metrics.json file."),
    ] = Path("generated_project/.autosd/metrics.json"),
) -> None:
    """Show sprint metrics snapshot."""
    metrics_store = MetricsStore(path=metrics_path)
    metrics_store.load()
    console.print_json(json.dumps(metrics_store.snapshot().__dict__, indent=2))


@sprint_app.command("run")
def sprint_run(
    requirements_file: Annotated[
        Path | None,
        typer.Option(help="Path to markdown/text requirements specification."),
    ] = None,
    requirements_text: Annotated[
        str | None,
        typer.Option(help="Inline requirements specification string."),
    ] = None,
    output_dir: Annotated[
        Path,
        typer.Option(help="Output directory for backlog artifacts."),
    ] = Path("generated_project"),
    provider: Annotated[
        str,
        typer.Option(help="Model provider to use: openai, resilient, or mock."),
    ] = "openai",
    model: Annotated[
        str,
        typer.Option(help="Model name when using OpenAI provider."),
    ] = "gpt-5.3-codex",
    mock_responses_file: Annotated[
        Path | None,
        typer.Option(help="JSON file of queued responses when provider=mock."),
    ] = None,
) -> None:
    """Run end-to-end Scrum planning and ceremonies."""
    requirements = _load_requirements(requirements_file, requirements_text)
    resolved_provider = _create_provider(provider, model, mock_responses_file)
    agent = SoftwareDevelopmentAgent(provider=resolved_provider)
    artifacts = agent.run_scrum_cycle(requirements=requirements, output_dir=output_dir)
    console.print(f"Sprint run artifacts: {artifacts}")
