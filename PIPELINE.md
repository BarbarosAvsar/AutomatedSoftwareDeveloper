# Pipeline Truth Map

This repository uses a single authoritative pipeline map defined in
`automated_software_developer/agent/pipeline/schema.py`. That module is referenced by
progress reporting to avoid drift between documentation and implementation. It also
publishes the JSON schema for pipeline events and statuses.

## Generator Pipeline

1. **Refine** -> draft, refine, validate, lock
2. **Plan** -> architecture, backlog, sprint_planning
3. **Sprint** -> stories_in_progress, stories_completed
4. **Gates** -> tests, quality_gates, security_scans
5. **Release** -> version_tag, artifacts
6. **Deploy** -> dev, staging, production
7. **Monitor** -> health_checks
8. **Learn** -> retrospective, template_proposals

## CI Pipeline

1. **Unified Sequential Action** -> install/update tooling, install deps, `autosd verify-factory`
2. **Unified Event Stream** -> `ci-unified-events.jsonl` captures all info/warning/error/critical lines
3. **Failure Indexing** -> `failed-jobs.json`, append-only ledger, dashboard update

Execution notes:

- `.github/workflows/unified-actions.yml` is the authoritative CI executor.
- `.github/workflows/unified-actions.yml` is the only workflow file used for CI execution.
- CI logic is executed by one sequential runner script: `scripts/ci/run_unified_action.py`.
- Failed workflow runs are documented in:
  - unified run artifact: `ci-unified-events.jsonl`
  - local append-only ledger: `.autosd/ci/failure_ledger.jsonl`
  - persistent issue: `CI Failure Dashboard` (`ci-failures` label, latest 30 failures)

## Pipeline Event Schema

Pipeline events must conform to `PIPELINE_EVENT_SCHEMA` in
`automated_software_developer/agent/pipeline/schema.py`, including:

- `event_id`, `timestamp`, `pipeline`, `step`, `status`
- status values: `not_started`, `in_progress`, `blocked`, `completed`, `failed`
