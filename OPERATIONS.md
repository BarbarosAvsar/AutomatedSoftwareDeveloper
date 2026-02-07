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

### 4) Revoke quickly during incidents

```bash
autosd preauth revoke <grant_id>
autosd halt --project my-project
```

## Audit Trail

Privileged actions are logged to:

- `~/.autosd/audit.log.jsonl`

Records include timestamp, action, project, grant id, result, and references (no secrets).

## Rollback and Resume

```bash
autosd rollback --project my-project --env staging --target generic_container
autosd resume --project my-project
```

## Routine Verification

```bash
python -m ruff check .
python -m mypy automated_software_developer
python -m pytest
```
