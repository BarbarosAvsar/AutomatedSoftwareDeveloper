"""Verification helpers for signed preauthorization grants."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from automated_software_developer.agent.preauth.grants import (
    PreauthGrant,
    load_grant,
    load_revoked_ids,
    verify_grant_signature,
)
from automated_software_developer.agent.preauth.keys import load_public_keys


@dataclass(frozen=True)
class GrantVerificationResult:
    """Result of grant validity and capability verification."""

    valid: bool
    reason: str
    grant: PreauthGrant | None


def verify_grant(
    *,
    grant_id: str,
    home_dir: Path | None = None,
    required_capability: str | None = None,
    project_id: str | None = None,
    environment: str | None = None,
    current_time: datetime | None = None,
) -> GrantVerificationResult:
    """Verify grant signature, expiry, revocation, scope, and capability."""
    grant = load_grant(grant_id, home_dir=home_dir)
    if grant is None:
        return GrantVerificationResult(valid=False, reason="grant_not_found", grant=None)

    revoked = load_revoked_ids(home_dir=home_dir)
    if grant.grant_id in revoked:
        return GrantVerificationResult(valid=False, reason="grant_revoked", grant=grant)

    now = current_time or datetime.now(tz=UTC)
    expires_at_raw = grant.payload.get("expires_at")
    if not isinstance(expires_at_raw, str):
        return GrantVerificationResult(valid=False, reason="invalid_expiry", grant=grant)
    try:
        expires_at = datetime.fromisoformat(expires_at_raw)
    except ValueError:
        return GrantVerificationResult(valid=False, reason="invalid_expiry", grant=grant)
    if now >= expires_at:
        return GrantVerificationResult(valid=False, reason="grant_expired", grant=grant)

    public_keys = load_public_keys(home_dir=home_dir)
    if not public_keys:
        return GrantVerificationResult(valid=False, reason="public_key_missing", grant=grant)
    if not verify_grant_signature(grant, public_keys):
        return GrantVerificationResult(valid=False, reason="invalid_signature", grant=grant)

    if project_id is not None and not _project_in_scope(grant, project_id):
        return GrantVerificationResult(valid=False, reason="project_out_of_scope", grant=grant)

    if environment is not None and not _environment_allowed(grant, environment):
        return GrantVerificationResult(valid=False, reason="environment_not_allowed", grant=grant)

    if required_capability is not None and not capability_allowed(grant, required_capability):
        return GrantVerificationResult(valid=False, reason="capability_not_allowed", grant=grant)

    return GrantVerificationResult(valid=True, reason="ok", grant=grant)


def capability_allowed(grant: PreauthGrant, capability: str) -> bool:
    """Return whether grant explicitly allows capability."""
    capabilities = grant.payload.get("capabilities")
    if not isinstance(capabilities, dict):
        return False
    value = capabilities.get(capability)
    return isinstance(value, bool) and value


def _project_in_scope(grant: PreauthGrant, project_id: str) -> bool:
    """Return whether project id is inside grant scope."""
    scope = grant.payload.get("scope")
    if not isinstance(scope, dict):
        return False
    project_ids = scope.get("project_ids")
    if project_ids == "*":
        return True
    if isinstance(project_ids, list):
        return project_id in {str(item) for item in project_ids}
    return False


def _environment_allowed(grant: PreauthGrant, environment: str) -> bool:
    """Return whether grant allows environment-specific deploy capabilities."""
    env = environment.strip().lower()
    capability_map = {
        "dev": "auto_deploy_dev",
        "staging": "auto_deploy_staging",
        "prod": "auto_deploy_prod",
    }
    required = capability_map.get(env)
    if required is None:
        return False
    return capability_allowed(grant, required)


def grant_break_glass(grant: PreauthGrant | None) -> bool:
    """Return whether grant is marked as break-glass."""
    if grant is None:
        return False
    value: Any = grant.payload.get("break_glass")
    return isinstance(value, bool) and value
