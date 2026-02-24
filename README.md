# Automated Software Developer

Autonomous software-factory agent for requirements refinement, planning, implementation, quality/security validation, deployment scaffolding, telemetry analytics, incident healing, and policy-gated operations.

## Quick Start

1) Install:

```bash
python -m pip install -e .[dev,security]
# Optional pinned toolchain:
# python -m pip install -r requirements-dev.lock -e .
```

2) Run an end-to-end workflow:

```bash
autosd run --requirements-file requirements.md --output-dir output/project
```

3) Check version and logs:

```bash
autosd --version
tail -f autosd.log
```

## Execution Modes

`autosd run` and `autosd daemon` support:

- `direct` (default): full refine -> implement -> verify pipeline.
- `planning`: requirements refinement + backlog + sprint planning artifacts only.
- `auto`: agent-selected mode. Current policy is deterministic planning-first (`auto -> planning`).

Examples:

```bash
autosd run --requirements-file requirements.md --execution-mode direct
autosd run --requirements-file requirements.md --execution-mode planning
autosd run --requirements-file requirements.md --execution-mode auto

autosd daemon --requirements-dir requirements --projects-dir projects --execution-mode auto
```

## Pipeline

`autosd run` remains backward-compatible (default `direct`) and supports planning-first operation.

Direct mode stages:

1. Requirements refinement (`.autosd/refined_requirements.md`)
2. Story backlog (`.autosd/backlog.json`)
3. Story execution loop (`.autosd/sprint_log.jsonl`)
4. Prompt journaling (`.autosd/prompt_journal.jsonl`)
5. Quality/security gates (ruff/mypy/pytest + optional bandit)
6. Platform capability planning (`.autosd/platform_plan.json`, `.autosd/capability_graph.json`)
7. Packaging/build planning (optional execution)
8. Provenance (`.autosd/provenance/build_manifest.json`, optional `sbom.json`)
9. Progress/design docs (`.autosd/progress.json`, `.autosd/design_doc.md`)

Planning mode stages:

1. Requirements refinement (`.autosd/refined_requirements.md`)
2. Scrum backlog (`.autosd/backlog.json`)
3. Sprint planning artifacts (`.autosd/sprints/<id>/sprint_plan.json`)

## Installation

```bash
python -m pip install -e .[dev,security]
```

Optional pinned local mirror of CI toolchain:

```bash
python -m pip install -r requirements-dev.lock -e .
```

## Core Commands

### Run / Refine / Learn

```bash
autosd run --requirements-file requirements.md --output-dir output/project
autosd run --requirements-file requirements.md --strict-readiness
autosd refine --requirements-file requirements.md --output-dir output/refined-only
autosd learn --journals output/project/.autosd/prompt_journal.jsonl --update-templates
```

Useful `run` flags:

- `--execution-mode direct|planning|auto`
- `--strict-readiness/--allow-readiness-gaps`
- `--preferred-platform web_app|api_service|cli_tool|desktop_app|mobile_app`
- `--execute-packaging/--plan-packaging`
- `--reproducible/--non-reproducible`
- `--conformance-seed <int>`
- `--parallel-prompt-workers <int>`
- `--allow-stale-parallel-prompts/--disallow-stale-parallel-prompts`
- `--sbom-mode off|if-available|required`
- `--security-scan --security-scan-mode off|if-available|required`
- `--gitops-enable --gitops-auto-push --gitops-tag-release`

### Factory Verification

```bash
autosd verify-factory
autosd verify-factory --strict-readiness
autosd verify-factory --conformance-provider openai --real-provider-required \
  --real-provider-model gpt-5.3-codex --smoke-fixtures cli_tool,api_service,web_app
```

Runs repository quality gates, workflow lint, CI mirror execution, and conformance suite. Produces `conformance/report.json` and `verify_factory_report.json`.

### Environment Doctor

```bash
autosd doctor
autosd doctor --require-openai-key
```

### Scrum Backlog & Sprint Automation

```bash
autosd backlog refine --requirements-file requirements.md --output-dir output/project
autosd sprint plan --backlog-path output/project/.autosd/backlog.json
autosd sprint start --sprint-plan-path output/project/.autosd/sprints/<id>/sprint_plan.json
autosd sprint review --backlog-path output/project/.autosd/backlog.json \
  --sprint-plan-path output/project/.autosd/sprints/<id>/sprint_plan.json
autosd sprint retro --sprint-plan-path output/project/.autosd/sprints/<id>/sprint_plan.json
autosd sprint metrics --metrics-path output/project/.autosd/metrics.json
autosd sprint run --requirements-file requirements.md --output-dir output/project
```

### Portfolio / Dashboard API

```bash
autosd projects list
autosd projects show <project_id>
autosd projects status --all
autosd projects retire <project_id>
autosd dashboard serve --host 127.0.0.1 --port 8765
```

### Patch Engine

```bash
autosd patch --project <id> --reason "security fix"
autosd patch-all --domain commerce --needs-upgrade --reason "dependency refresh"
```

### Deployment

```bash
autosd deploy --project <id> --env staging --target generic_container
autosd deploy --project <id> --env staging --target generic_container --execute \
  --health-check-command "python -m pytest -q tests/smoke" --health-timeout-seconds 180
autosd rollback --project <id> --env staging --target generic_container
autosd promote --project <id> --from staging --to prod --target generic_container
```

### Release Bundles

```bash
autosd release --project <id> --version 1.2.3 --tag v1.2.3
```

### Daemon Mode

```bash
autosd daemon --requirements-dir requirements --projects-dir projects --max-cycles 1 --execution-mode auto
```

### Telemetry (privacy-safe)

Telemetry is OFF by default.

```bash
autosd telemetry enable --project <id> --mode anonymous --retention-days 30
autosd telemetry enable --project <id> --mode off
autosd telemetry report --project <id>
autosd telemetry report-all --domain commerce
```

### Preauthorization (Signed Grants)

```bash
autosd preauth init-keys
autosd preauth create-grant --project-ids <id> --auto-deploy-prod --expires-in-hours 1
autosd preauth list --active-only
autosd preauth show <grant_id>
autosd preauth revoke <grant_id>
autosd preauth rotate-keys
```

### Policy Introspection

```bash
autosd policy show --project <project_id>
autosd policy show --preauth-grant <grant_id> --env prod
```

## CI / Verification

Local gates:

```bash
python -m ruff check .
python -m mypy automated_software_developer
python -m pytest
```

GitHub Actions model:

- `Unified Actions` (`.github/workflows/unified-actions.yml`) is the single authoritative CI workflow.
- It runs a single sequential CI action (`scripts/ci/run_unified_action.py`) that executes all gates in order.
- Primary per-run artifact is one unified event file:
  - `ci-unified-events.jsonl` (all `info`, `warning`, `error`, `critical` lines in one stream)
- Additional outputs:
  - `ci-unified-summary.md`
  - `failed-jobs.json`
  - `.autosd/ci/failure_ledger.jsonl`
  - `verify_factory_report.json`
  - `conformance/report.json`
  - `conformance/report-real-provider.json` (blocking real-provider smoke on PR + nightly)
- Failed runs are also indexed in persistent GitHub issue: `CI Failure Dashboard` (label `ci-failures`, latest 30 failures)

## Observability & Logs

AutoSD writes a local debug log to `autosd.log` (override with `--log-file`).

```bash
autosd --verbose run --requirements-file requirements.md
```

## In-Repo Skills

- `skills/agile-requirements-refiner/SKILL.md`
- `skills/story-implementer-with-tests/SKILL.md`
