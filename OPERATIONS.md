# OPERATIONS.md

## Safe Autonomy with Preauth Grants

Use signed grants for non-interactive privileged autonomy.

### 1) Initialize keys

```bash
autosd preauth init-keys
```

### 2) Create least-privilege grant

Staging-only example:

```bash
autosd preauth create-grant \
  --project-ids my-project \
  --auto-deploy-dev \
  --auto-deploy-staging \
  --no-auto-deploy-prod \
  --expires-in-hours 2
```

Prod deploy example with stricter scope:

```bash
autosd preauth create-grant \
  --project-ids my-project \
  --auto-deploy-prod \
  --auto-rollback \
  --expires-in-hours 1
```

Break-glass example (short expiry enforced):

```bash
autosd preauth create-grant \
  --project-ids my-project \
  --auto-deploy-prod \
  --break-glass \
  --expires-in-hours 2
```

### 3) Use grant in operations

```bash
autosd deploy --project my-project --env prod --target generic_container --preauth-grant <grant_id>
autosd patch --project my-project --auto-push --preauth-grant <grant_id>
autosd heal --project my-project --target generic_container --preauth-grant <grant_id>
```

### 4) Review or revoke grants

```bash
autosd preauth list --active-only
autosd preauth revoke <grant_id>
autosd halt --project my-project
```

## Deploy, Rollback, Promote

Destructive actions prompt for confirmation unless `--force` is provided:

```bash
autosd deploy --project my-project --env prod --target docker --preauth-grant <grant_id> --force
autosd rollback --project my-project --env staging --target generic_container --force
autosd promote --project my-project --from staging --to prod --target generic_container --force
```

## Incident Healing & Postmortems

```bash
autosd incidents list
autosd heal --project my-project --target generic_container --env staging
```

Postmortems are written to `.autosd/postmortems/` inside the project.

## Audit Trail & Logs

Privileged actions are logged to:

- `~/.autosd/audit.log.jsonl`

Operational debug logs are written to:

- `autosd.log` (override with `--log-file`)

## Policy Visibility

Inspect resolved policy and preauth status (read-only):

```bash
autosd policy show --project my-project
autosd policy show --preauth-grant <grant_id> --env prod
```

## Parallel Prompt Execution & Rate Limits

Prompt execution can be prefetched in parallel during sprint loops to improve throughput:

```bash
autosd run --parallel-prompt-workers 4
```

By default, prefetched prompts are discarded if the workspace changes between prefetch and
execution. Use `--allow-stale-parallel-prompts` only when you accept the risk of stale
context (the system will still retry with a fresh prompt if verification fails).

When model rate limits are hit, the OpenAI provider respects `retry-after` or reset
headers when present, otherwise it uses bounded exponential backoff. Retries are capped,
so if limits do not reset in time the run will fail fast and surface the last error for
operator review. Use `--verbose` and `autosd.log` for detailed timing and retry data.

## Routine Verification

```bash
python -m ruff check .
python -m mypy automated_software_developer
python -m pytest
```

## Factory Release Gate

Run the full generator + conformance gate in one step:

```bash
autosd verify-factory
```

The reports are written to `conformance/report.json` and `verify_factory_report.json`.
Use `--verbose` for additional debug logging in `autosd.log`.

### CI Troubleshooting

- Run the same CI entrypoint locally:
  - `./ci/run_ci.sh`
- Lint workflows locally:
  - `autosd ci lint-workflows`
- If CI mirror fails, inspect `verify_factory_report.json` for the failing gate.
- Use the `CI Failure Dashboard` issue (label `ci-failures`) as the single-click failure index
  across workflows. The dashboard keeps the latest 30 failed runs with links and failed-job names.
- For legacy workflow checks (`ci-build`, `policy`, `sbom`, `verify-factory`), failures are mirrored
  from `Unified Actions` job results by compatibility shim workflows.


## Operational SLOs / SLIs

Track these baseline service indicators for autonomous runs and incident handling:

- **Run Success SLI**: percentage of `autosd run` executions that complete without failed stories.
  - **SLO target**: >= 95% over rolling 7 days.
- **Verification Pass SLI**: percentage of release-gated checks (`ruff`, `mypy`, `pytest`, `verify-factory`) that pass on first attempt.
  - **SLO target**: >= 90% over rolling 14 days.
- **Policy Enforcement SLI**: percentage of privileged operations that require and validate preauth grants when policy requires it.
  - **SLO target**: 100% (no bypasses).
- **Incident Recovery SLI**: time-to-recovery for auto-heal or manual rollback from incident open to mitigated state.
  - **SLO target**: p95 <= 30 minutes.

Record metrics in sprint retrospectives and incident postmortems for trend review.

## CLI Error Codes and Remediation

Common CLI validation errors include stable codes to speed troubleshooting:

- `AUTOSD-PREAUTH-REQUIRED`: privileged command requires a grant.
  - Remediation: create a signed grant (`autosd preauth create-grant`) and pass `--preauth-grant`.
- `AUTOSD-PREAUTH-INVALID`: grant verification failed (revoked/expired/scope/capability mismatch).
  - Remediation: run `autosd preauth list --active-only`, then retry with a valid grant.
- `AUTOSD-ENV-INVALID`: invalid deploy environment value.
  - Remediation: use `--env dev|staging|prod`.
- `AUTOSD-TARGET-ENV-INVALID`: invalid promotion target environment.
  - Remediation: use `--to dev|staging|prod`.
