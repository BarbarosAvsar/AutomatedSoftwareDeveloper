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
