# Automated Software Developer

Autonomous software-factory agent for requirements refinement, story-based implementation, quality/security validation, deployment scaffolding, telemetry analytics, incident healing, and policy-gated operations.

## Quick Start

1) Install:

```bash
python -m pip install -e .[dev]
```

2) Run an end-to-end workflow:

```bash
autosd run --requirements-file requirements.md --output-dir output/project
```

3) Check your version and logs:

```bash
autosd --version
tail -f autosd.log
```

## Autonomous Engineering Console (UI)

The UI is a first-class, chat-first web console that exposes the full autonomous
workflow. The CLI remains fully supported.

### Windows 11 One-Click UI Setup

Prerequisites:

- Python 3.11+
- Node.js LTS
- npm (installed with Node.js)

Install AutoSD for local development:

```bash
py -3.11 -m pip install -e .[dev]
```

Start backend + frontend with one command:

```bash
autosd ui serve
```

Install desktop launcher shortcuts (per-user, no admin required):

```bash
autosd ui install-shortcuts
```

Remove desktop launcher shortcuts:

```bash
autosd ui remove-shortcuts
```

Optional global-style install using pipx:

```bash
py -3.11 -m pip install --user pipx
py -3.11 -m pipx ensurepath
pipx install --editable .
```

Troubleshooting:

- PowerShell execution policy blocks scripts: run with `powershell -ExecutionPolicy Bypass -File scripts/start_ui.ps1`.
- PATH issues for `autosd` or `npm`: reopen terminal after install and confirm with `where autosd` / `where npm`.
- Port conflicts: override defaults with `autosd ui serve --backend-port 18080 --frontend-port 5174`.
- Use `autosd.log` and `--verbose` for richer diagnostics (for example: `autosd --verbose ui serve`).

### Legacy Manual UI Startup (still supported)

Backend API (FastAPI):

```bash
python -m uvicorn ui.backend.app:app --reload --port 8080
```

Frontend (Vite + React):

```bash
cd ui/frontend
npm install
npm run dev
```

## Security Posture

This system is **risk-reduced and hardened** (not guaranteed secure). It enforces:

- path traversal protection and command safety filtering
- secret redaction/scanning for journals/logs/artifacts
- privacy-safe telemetry (off by default)
- policy + preauthorization gating for high-risk actions

Residual risk still exists and requires human governance.

## Pipeline

`autosd run` remains backward-compatible and now includes additional artifacts/capabilities:

1. Requirements refinement (`.autosd/refined_requirements.md`)
2. Story backlog planning (`.autosd/backlog.json`)
3. Story-by-story sprint execution (`.autosd/sprint_log.jsonl`)
4. Prompt journaling (`.autosd/prompt_journal.jsonl`)
5. Quality/security gates (ruff/mypy/pytest + optional bandit)
6. Platform capability planning (`.autosd/platform_plan.json`, `.autosd/capability_graph.json`)
7. Packaging/build planning (optional execution)
8. Provenance output (`.autosd/provenance/build_manifest.json`, optional `sbom.json`)
9. Progress/design docs (`.autosd/progress.json`, `.autosd/design_doc.md`)

## Installation

```bash
python -m pip install -e .[dev]
```

Optional security extras:

```bash
python -m pip install -e .[security]
```

## Core Commands

### Run / Refine / Learn

```bash
autosd run --requirements-file requirements.md --output-dir output/project
autosd refine --requirements-file requirements.md --output-dir output/refined-only
autosd learn --journals output/project/.autosd/prompt_journal.jsonl --update-templates
```

Useful `run` flags:

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
```

This runs repository quality gates, workflow lint, CI mirror execution, and the
conformance suite. It produces `conformance/report.json` and
`verify_factory_report.json`, failing fast if any generator or fixture gate fails.

### Scrum Backlog & Sprint Automation

```bash
autosd backlog refine --requirements-file requirements.md --output-dir output/project
autosd sprint plan --backlog-path output/project/.autosd/backlog.json
autosd sprint start --sprint-plan-path output/project/.autosd/sprints/<id>/sprint_plan.json
autosd sprint review --backlog-path output/project/.autosd/backlog.json \\
  --sprint-plan-path output/project/.autosd/sprints/<id>/sprint_plan.json
autosd sprint retro --sprint-plan-path output/project/.autosd/sprints/<id>/sprint_plan.json
autosd sprint metrics --metrics-path output/project/.autosd/metrics.json
autosd sprint run --requirements-file requirements.md --output-dir output/project
```

### Portfolio / Dashboard

```bash
autosd projects list
autosd projects show <project_id>
autosd projects status --all
autosd projects retire <project_id>
autosd dashboard serve --host 127.0.0.1 --port 8765
```

Dashboard endpoints include `/health`, `/projects`, `/projects/<id>`, and `/oversight`
for governance-aware oversight summaries.

### Patch Engine (single/all)

```bash
autosd patch --project <id> --reason "security fix"
autosd patch-all --domain commerce --needs-upgrade --reason "dependency refresh"
```

### Deployment

```bash
autosd deploy --project <id> --env staging --target generic_container
autosd rollback --project <id> --env staging --target generic_container
autosd promote --project <id> --from staging --to prod --target generic_container
```

Notes:

- Production deploy/promote and rollback prompts for confirmation unless `--force` is provided.
- Production deploys require a valid preauth grant (`--preauth-grant`).

Implemented targets:

- `docker`
- `github_pages`
- `generic_container`

### Release Bundles

```bash
autosd release --project <id> --version 1.2.3 --tag v1.2.3
```

Release artifacts are stored under `.autosd/releases/` within each project.

### Daemon Mode (Zero Interaction)

```bash
autosd daemon --requirements-dir requirements --projects-dir projects --max-cycles 1
```

Daemon mode watches for requirement files and runs the full company workflow
in a non-interactive loop (policy-gated). Use `--max-cycles 0` for continuous operation.

### Telemetry (privacy-safe)

Telemetry is OFF by default.

```bash
autosd telemetry enable --project <id> --mode anonymous --retention-days 30
autosd telemetry enable --project <id> --mode off
autosd telemetry report --project <id>
autosd telemetry report-all --domain commerce
```

Project-side event file (schema-validated):

- `.autosd/telemetry/events.jsonl`

Local warehouse:

- `~/.autosd/telemetry.db`

### Policy Introspection

```bash
autosd policy show --project <project_id>
autosd policy show --preauth-grant <grant_id> --env prod
```

### Incidents / Self-Healing

```bash
autosd incidents list
autosd incidents show <incident_id>
autosd heal --project <id> --target generic_container --env staging
```

Postmortems:

- `.autosd/postmortems/<incident_id>.md`

### Kill Switch

```bash
autosd halt --project <id>
autosd resume --project <id>
```

## Preauthorization (Signed Grants)

High-risk autonomy uses signed local grants.

```bash
autosd preauth init-keys
autosd preauth create-grant --project-ids <id> --auto-deploy-prod --expires-in-hours 1
autosd preauth list --active-only
autosd preauth show <grant_id>
autosd preauth revoke <grant_id>
autosd preauth rotate-keys
```

Operational commands support:

- `--require-preauth`
- `--preauth-grant <grant_id>`

Default safety rule: production deploy is blocked unless a valid grant explicitly allows it.

## Observability & Logs

AutoSD writes a local debug log to `autosd.log` (override with `--log-file`).

```bash
autosd --verbose run --requirements-file requirements.md
```

## Learning Model

Learning is bounded and reviewable:

- journal-driven proposals are generated first
- versioned prompt templates are updated only when explicitly requested
- prior template versions remain available for rollback

Artifacts:

- `PROMPT_PLAYBOOK.md`
- `PROMPT_TEMPLATE_CHANGES.md`
- `automated_software_developer/agent/prompt_patterns/*.v*.json`

## CI / Local Verification

```bash
python -m ruff check .
python -m mypy automated_software_developer
python -m pytest
```

### GitHub Actions Model

- `Unified Actions` (`.github/workflows/unified-actions.yml`) is the single authoritative CI workflow.
- `Unified Actions` is the only workflow definition in `.github/workflows/`.
- Failed runs are aggregated into one persistent GitHub issue (`CI Failure Dashboard`, label `ci-failures`)
  with the latest 30 failures and direct run links.

## In-Repo Skills

- `skills/agile-requirements-refiner/SKILL.md`
- `skills/story-implementer-with-tests/SKILL.md`
