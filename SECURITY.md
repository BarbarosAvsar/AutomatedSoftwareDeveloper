# SECURITY.md

## Security Model

This project is hardened and risk-reduced, not perfectly secure.

Primary controls:

- strict workspace path traversal protection
- unsafe command filtering
- secret scanning/redaction for journals/logs/artifacts
- append-only operational logs for traceability
- policy + signed preauthorization gating for privileged actions
- telemetry privacy validation with explicit allowlists

## Threat Notes

Residual risks include:

- model misinterpretation of requirements
- third-party dependency vulnerabilities
- deployment misconfiguration outside generator control

Use human review for high-impact releases.

## Sensitive Data Rules

- Never commit secrets, private keys, or tokens.
- Telemetry must not include PII/IP/user content.
- Keep preauth private keys local (`~/.autosd/preauth/keys/private_key.pem`).
- CI workflows must pin action versions and avoid printing environment variables or secrets.
- CI permissions are least-privilege (explicit `permissions: { contents: read }` unless needed).

## Incident Response

- Revoke compromised grants immediately:
  - `autosd preauth revoke <grant_id>`
- Halt affected project automation:
  - `autosd halt --project <id>`
- Run healing pipeline and review postmortem:
  - `autosd heal --project <id>`
- Inspect logs:
  - `tail -f autosd.log`

## Verification

```bash
python -m ruff check .
python -m mypy automated_software_developer
python -m pytest
```
