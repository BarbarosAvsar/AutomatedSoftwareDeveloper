"""CLI command registrations."""

from __future__ import annotations

# mypy: ignore-errors
# ruff: noqa: B008,F403,F405,I001
from automated_software_developer.commands.common import *


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Show AutoSD version and exit.",
            is_eager=True,
            callback=_version_callback,
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose debug logging."),
    ] = False,
    log_file: Annotated[
        Path,
        typer.Option("--log-file", help="Write logs to autosd.log (default: ./autosd.log)."),
    ] = Path("autosd.log"),
) -> None:
    """Autonomous software-development agent CLI with policy-gated operations."""
    configure_logging(log_file=log_file, verbose=verbose)


@app.command()
def run(
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
        typer.Option(help="Output directory for the generated software project."),
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
    max_task_attempts: Annotated[
        int,
        typer.Option(help="Maximum retries per story when verification fails."),
    ] = 4,
    timeout_seconds: Annotated[
        int,
        typer.Option(help="Timeout for each verification command."),
    ] = 240,
    max_stories_per_sprint: Annotated[
        int,
        typer.Option(help="Maximum stories selected per sprint iteration."),
    ] = 2,
    parallel_prompt_workers: Annotated[
        int,
        typer.Option(help="Parallel worker count for prompt prefetching."),
    ] = 1,
    allow_stale_parallel_prompts: Annotated[
        bool,
        typer.Option(
            "--allow-stale-parallel-prompts/--disallow-stale-parallel-prompts",
            help="Allow parallel prompt prefetch responses even if workspace changed.",
        ),
    ] = False,
    enable_learning: Annotated[
        bool,
        typer.Option(
            "--enable-learning/--disable-learning",
            help="Opt-in local learning pass from current run journal.",
        ),
    ] = False,
    update_templates: Annotated[
        bool,
        typer.Option(
            "--update-templates/--no-update-templates",
            help="When learning is enabled, allow versioned prompt template updates.",
        ),
    ] = False,
    preferred_platform: Annotated[
        str | None,
        typer.Option(
            help=(
                "Optional platform adapter override "
                "(web_app, api_service, cli_tool, desktop_app, mobile_app)."
            ),
        ),
    ] = None,
    execute_packaging: Annotated[
        bool,
        typer.Option(
            "--execute-packaging/--plan-packaging",
            help="Execute platform build/package commands (default: plan only).",
        ),
    ] = False,
    quality_gates: Annotated[
        bool,
        typer.Option(
            "--quality-gates/--no-quality-gates",
            help="Enable style/lint/type quality gates in story verification.",
        ),
    ] = True,
    enforce_docstrings: Annotated[
        bool,
        typer.Option(
            "--enforce-docstrings/--no-enforce-docstrings",
            help="Require docstrings for generated public Python functions/classes.",
        ),
    ] = True,
    security_scan: Annotated[
        bool,
        typer.Option(
            "--security-scan/--no-security-scan",
            help="Enable optional security scanning (Bandit when available).",
        ),
    ] = False,
    security_scan_mode: Annotated[
        str,
        typer.Option(
            help="Security scan behavior: off, if-available, required.",
        ),
    ] = "if-available",
    reproducible: Annotated[
        bool,
        typer.Option(
            "--reproducible/--non-reproducible",
            help="Enable reproducible mode metadata and deterministic build intent.",
        ),
    ] = False,
    conformance_seed: Annotated[
        int | None,
        typer.Option(
            "--conformance-seed",
            help="Optional seed override for reproducible runs and conformance checks.",
        ),
    ] = None,
    sbom_mode: Annotated[
        str,
        typer.Option(help="SBOM behavior: off, if-available, required."),
    ] = "if-available",
    gitops_enable: Annotated[
        bool,
        typer.Option(
            "--gitops-enable/--gitops-disable",
            help="Enable local Git commit/tag after successful run.",
        ),
    ] = False,
    gitops_auto_push: Annotated[
        bool,
        typer.Option(
            "--gitops-auto-push/--gitops-no-auto-push",
            help="Push generated project branch when gitops is enabled.",
        ),
    ] = False,
    gitops_tag_release: Annotated[
        bool,
        typer.Option(
            "--gitops-tag-release/--gitops-no-tag-release",
            help="Create a version tag after successful run when gitops is enabled.",
        ),
    ] = True,
) -> None:
    """Run the full autonomous refine -> implement -> verify workflow.

    Examples:
        autosd run --requirements-file requirements.md --output-dir output/project
        autosd run --requirements-text "Build a CLI" --provider mock \\
          --mock-responses-file mocks.json
    """
    requirements = _load_requirements(requirements_file, requirements_text)
    resolved_provider = _create_provider(provider, model, mock_responses_file)
    max_task_attempts = _ensure_positive(max_task_attempts, "max-task-attempts")
    timeout_seconds = _ensure_positive(timeout_seconds, "timeout-seconds")
    max_stories_per_sprint = _ensure_positive(max_stories_per_sprint, "max-stories-per-sprint")
    parallel_prompt_workers = _ensure_positive(
        parallel_prompt_workers,
        "parallel-prompt-workers",
    )
    security_scan_mode = _validate_security_scan_mode(security_scan_mode)
    sbom_mode = _validate_sbom_mode(sbom_mode)
    if conformance_seed is not None:
        conformance_seed = _ensure_positive(conformance_seed, "conformance-seed")
    config = AgentConfig(
        max_task_attempts=max_task_attempts,
        command_timeout_seconds=timeout_seconds,
        max_stories_per_sprint=max_stories_per_sprint,
        enforce_quality_gates=quality_gates,
        enforce_docstrings=enforce_docstrings,
        enable_security_scan=security_scan,
        security_scan_mode=security_scan_mode,
        enable_learning=enable_learning,
        update_templates=update_templates,
        preferred_platform=preferred_platform,
        execute_packaging=execute_packaging,
        reproducible=reproducible,
        sbom_mode=sbom_mode,
        prompt_seed_base=conformance_seed
        if conformance_seed is not None
        else AgentConfig().prompt_seed_base,
        parallel_prompt_workers=parallel_prompt_workers,
        allow_stale_parallel_prompts=allow_stale_parallel_prompts,
    )
    agent = SoftwareDevelopmentAgent(provider=resolved_provider, config=config)

    summary = agent.run(requirements=requirements, output_dir=output_dir)
    table = Table(title="Autonomous Development Summary")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Output Directory", str(summary.output_dir))
    table.add_row("Project Name", summary.project_name)
    table.add_row("Stories Completed", f"{summary.tasks_completed}/{summary.tasks_total}")
    table.add_row("Stack Rationale", summary.stack_rationale)
    table.add_row("Files Changed", str(len(summary.changed_files)))
    if summary.refined_spec_path is not None:
        table.add_row("Refined Spec", str(summary.refined_spec_path))
    if summary.backlog_path is not None:
        table.add_row("Backlog", str(summary.backlog_path))
    if summary.design_doc_path is not None:
        table.add_row("Design Doc", str(summary.design_doc_path))
    if summary.sprint_log_path is not None:
        table.add_row("Sprint Log", str(summary.sprint_log_path))
    if summary.journal_path is not None:
        table.add_row("Prompt Journal", str(summary.journal_path))
    if summary.platform_plan_path is not None:
        table.add_row("Platform Plan", str(summary.platform_plan_path))
    if summary.capability_graph_path is not None:
        table.add_row("Capability Graph", str(summary.capability_graph_path))
    if summary.architecture_doc_path is not None:
        table.add_row("Architecture Doc", str(summary.architecture_doc_path))
    if summary.architecture_components_path is not None:
        table.add_row("Architecture Components", str(summary.architecture_components_path))
    if summary.architecture_adrs_path is not None:
        table.add_row("Architecture ADRs", str(summary.architecture_adrs_path))
    if summary.build_hash_path is not None:
        table.add_row("Build Hash", str(summary.build_hash_path))
    console.print(table)

    console.print("\nVerification commands:")
    for result in summary.verification_results:
        status = "PASS" if result.passed else "FAIL"
        console.print(f"[{status}] {result.command} ({result.duration_seconds:.2f}s)")

    if gitops_enable:
        manager = GitOpsManager()
        tag = "v0.1.0" if gitops_tag_release else None
        git_result = manager.commit_push_tag(
            repo_dir=summary.output_dir,
            message=f"chore(run): autosd generated {summary.project_name}",
            branch=None,
            auto_push=gitops_auto_push,
            tag=tag,
        )
        console.print("\nGitOps:")
        console.print(f"- committed: {git_result.committed}")
        console.print(f"- pushed: {git_result.pushed}")
        console.print(f"- pending_push: {git_result.pending_push}")
        console.print(f"- commit_sha: {git_result.commit_sha or '-'}")


@app.command("verify-factory")
def verify_factory(
    conformance_seed: Annotated[
        int,
        typer.Option(
            "--conformance-seed",
            help="Seed for reproducible conformance generation runs.",
        ),
    ] = 4242,
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            help="Directory to write generated conformance projects.",
        ),
    ] = Path("conformance/output"),
    report_path: Annotated[
        Path,
        typer.Option(
            "--report-path",
            help="Path to write the conformance report JSON.",
        ),
    ] = Path("conformance/report.json"),
    diff_check: Annotated[
        bool,
        typer.Option(
            "--diff-check/--no-diff-check",
            help="Generate fixtures twice and compare outputs for determinism.",
        ),
    ] = True,
    skip_generator_gates: Annotated[
        bool,
        typer.Option(
            "--skip-generator-gates/--run-generator-gates",
            help="Skip repo-level ruff/mypy/pytest gates before conformance.",
        ),
    ] = False,
    max_workers: Annotated[
        int,
        typer.Option(help="Parallel worker count for conformance fixtures."),
    ] = 3,
    verify_report_path: Annotated[
        Path,
        typer.Option(
            "--verify-report-path",
            help="Path to write the verify-factory report JSON.",
        ),
    ] = Path("verify_factory_report.json"),
) -> None:
    """Run generator and generated-project quality gates for release readiness."""
    conformance_seed = _ensure_positive(conformance_seed, "conformance-seed")
    max_workers = _ensure_positive(max_workers, "max-workers")
    verify_report: dict[str, Any] = {
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "generator_gates": [],
        "workflow_lint": {},
        "ci_mirror": {},
        "conformance": {},
    }
    if not skip_generator_gates:
        gates = [
            ["python", "-m", "ruff", "check", "."],
            ["python", "-m", "mypy", "automated_software_developer"],
            ["python", "-m", "pytest"],
        ]
        for args in gates:
            command = " ".join(args)
            passed, duration = _run_gate_command(args)
            status = "PASS" if passed else "FAIL"
            console.print(f"[{status}] {command} ({duration:.2f}s)")
            verify_report["generator_gates"].append(
                {"command": command, "passed": passed, "duration_seconds": duration}
            )
            if not passed:
                _write_verify_report(verify_report_path, verify_report)
                raise typer.Exit(code=1)

    workflow_results = lint_workflows(Path("."))
    workflow_errors = [
        {"path": str(result.path), "errors": list(result.errors)}
        for result in workflow_results
        if not result.passed
    ]
    verify_report["workflow_lint"] = {
        "passed": not workflow_errors,
        "errors": workflow_errors,
    }
    if workflow_errors:
        console.print("[FAIL] Workflow lint failed.")
        _write_verify_report(verify_report_path, verify_report)
        raise typer.Exit(code=1)
    console.print("[PASS] Workflow lint passed.")

    mirror_result = run_ci_mirror(Path("."))
    verify_report["ci_mirror"] = {
        "passed": mirror_result.passed,
        "exit_code": mirror_result.exit_code,
        "duration_seconds": mirror_result.duration_seconds,
    }
    if not mirror_result.passed:
        console.print("[FAIL] CI mirror failed.")
        _write_verify_report(verify_report_path, verify_report)
        raise typer.Exit(code=1)
    console.print("[PASS] CI mirror passed.")

    report = run_conformance_suite(
        config=ConformanceConfig(
            output_dir=output_dir,
            report_path=report_path,
            conformance_seed=conformance_seed,
            diff_check=diff_check,
            max_workers=max_workers,
        )
    )
    status = "PASS" if report.passed else "FAIL"
    console.print(f"[{status}] Conformance suite complete. Report: {report_path}")
    verify_report["conformance"] = {
        "passed": report.passed,
        "report_path": str(report_path),
        "output_dir": str(output_dir),
    }
    _write_verify_report(verify_report_path, verify_report)
    if not report.passed:
        raise typer.Exit(code=1)


@app.command()
def refine(
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
        typer.Option(help="Output directory where refined artifact is written."),
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
    """Run only autonomous requirements refinement.

    Examples:
        autosd refine --requirements-file requirements.md --output-dir output/refined
        autosd refine --requirements-text "API for inventory tracking"
    """
    requirements = _load_requirements(requirements_file, requirements_text)
    resolved_provider = _create_provider(provider, model, mock_responses_file)
    agent = SoftwareDevelopmentAgent(provider=resolved_provider)
    refined = agent.refine_requirements(requirements=requirements, output_dir=output_dir)
    artifact_path = output_dir / ".autosd" / "refined_requirements.md"
    console.print(f"Refined specification written to: {artifact_path}")
    console.print(f"Stories identified: {len(refined.stories)}")


@app.command()
def learn(
    journals: Annotated[
        list[Path],
        typer.Option(
            "--journals",
            help="One or more prompt_journal.jsonl paths.",
        ),
    ],
    update_templates: Annotated[
        bool,
        typer.Option(
            "--update-templates/--no-update-templates",
            help="Persist incremented prompt template versions from journal signals.",
        ),
    ] = False,
    changelog_path: Annotated[
        Path,
        typer.Option(help="Path for human-readable prompt template change log."),
    ] = Path("PROMPT_TEMPLATE_CHANGES.md"),
) -> None:
    """Summarize journal history and optionally update versioned prompt templates.

    Examples:
        autosd learn --journals output/.autosd/prompt_journal.jsonl
        autosd learn --journals output/.autosd/prompt_journal.jsonl --update-templates
    """
    if not journals:
        raise typer.BadParameter("Provide at least one --journals path.")
    store = PromptPatternStore()
    summary = learn_from_journals(
        journal_paths=journals,
        pattern_store=store,
        update_templates=update_templates,
        playbook_path=Path("PROMPT_PLAYBOOK.md"),
        changelog_path=changelog_path,
    )
    table = Table(title="Learning Summary")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Entries Processed", str(summary.entries_processed))
    table.add_row("Templates Considered", str(summary.templates_considered))
    table.add_row("Template Proposals", str(len(summary.proposals)))
    table.add_row("Template Updates", str(len(summary.updates)))
    table.add_row("Failure Signals", json.dumps(summary.failure_signals))
    table.add_row("Change Log", str(summary.changelog_path))
    console.print(table)
    if summary.proposals:
        console.print("\nTemplate proposals:")
        for proposal in summary.proposals:
            console.print(
                f"- {proposal.template_id} (base v{proposal.base_version}): {proposal.reason}"
            )
    if summary.updates:
        console.print("\nTemplate updates:")
        for update in summary.updates:
            console.print(
                f"- {update.template_id}: v{update.old_version} -> v{update.new_version} "
                f"({update.path})"
            )


@app.command("daemon")
def daemon(
    requirements_dir: Annotated[
        Path,
        typer.Option(help="Directory to watch for new requirements files."),
    ] = Path("requirements"),
    projects_dir: Annotated[
        Path,
        typer.Option(help="Directory to write generated projects."),
    ] = Path("projects"),
    registry_path: Annotated[
        Path,
        typer.Option(help="Registry JSONL path for portfolio updates."),
    ] = Path(".autosd_portfolio/registry.jsonl"),
    incidents_path: Annotated[
        Path,
        typer.Option(help="Incident log JSONL path."),
    ] = Path(".autosd/incidents.jsonl"),
    incident_signals_path: Annotated[
        Path | None,
        typer.Option(help="Optional JSON list of incident signals to process."),
    ] = None,
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
    environment: Annotated[
        str,
        typer.Option(help="Deployment environment to target."),
    ] = "staging",
    deploy_target: Annotated[
        str,
        typer.Option(help="Deployment target ID."),
    ] = "generic_container",
    execute_deploy: Annotated[
        bool,
        typer.Option(
            "--execute-deploy/--scaffold-deploy",
            help="Execute deploy steps when possible.",
        ),
    ] = False,
    max_cycles: Annotated[
        int,
        typer.Option(help="Maximum daemon cycles (0 for infinite)."),
    ] = 1,
    interval_seconds: Annotated[
        int,
        typer.Option(help="Sleep interval between cycles."),
    ] = 5,
) -> None:
    """Run the non-interactive autonomous company workflow daemon."""
    resolved_provider = _create_provider(provider, model, mock_responses_file)
    config = DaemonConfig(
        requirements_dir=requirements_dir,
        projects_dir=projects_dir,
        registry_path=registry_path,
        incidents_path=incidents_path,
        incident_signals_path=incident_signals_path,
        environment=environment,
        deploy_target=deploy_target,
        execute_deploy=execute_deploy,
    )
    daemon_runner = CompanyDaemon(provider=resolved_provider, config=config)
    cycles_run = 0
    while True:
        processed = daemon_runner.run_once()
        console.print(f"Daemon cycle complete. Projects processed: {len(processed)}")
        cycles_run += 1
        if max_cycles and cycles_run >= max_cycles:
            break
        if interval_seconds > 0:
            import time

            time.sleep(interval_seconds)
