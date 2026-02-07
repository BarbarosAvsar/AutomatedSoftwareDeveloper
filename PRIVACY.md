# PRIVACY.md

## Telemetry Defaults

- Telemetry is OFF by default.
- When enabled, data is schema-validated, privacy-preserving, and allowlist-based.

## Prohibited Data

Never collect/store:

- PII
- IP addresses
- device fingerprints
- raw request payloads
- user-generated content

## Allowed Metrics (Policy-Governed)

- performance timings
- feature usage counters
- crash/error counts
- coarse platform metadata

## Retention

Default retention is 30 days unless policy changes it.

## Local Storage

- project events: `.autosd/telemetry/events.jsonl`
- local warehouse: `~/.autosd/telemetry.db`

## Examples

Enable or disable telemetry:

```bash
autosd telemetry enable --project <id> --mode anonymous --retention-days 30
autosd telemetry enable --project <id> --mode off
```

Generate a local report:

```bash
autosd telemetry report --project <id>
```
