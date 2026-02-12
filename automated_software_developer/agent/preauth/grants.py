"""Preauthorization grant model, signing, persistence, and revocation."""

from __future__ import annotations

import base64
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from automated_software_developer.agent.preauth.keys import key_paths, resolve_preauth_home


@dataclass(frozen=True)
class GrantPaths:
    """Filesystem paths used for grant and revocation persistence."""

    grants_dir: Path
    revoked_file: Path


def resolve_grant_paths(home_dir: Path | None = None) -> GrantPaths:
    """Resolve grant directories and revocation file."""
    home = (home_dir or resolve_preauth_home()).expanduser().resolve()
    grants_dir = home / "grants"
    revoked_file = home / "revoked.jsonl"
    grants_dir.mkdir(parents=True, exist_ok=True)
    revoked_file.parent.mkdir(parents=True, exist_ok=True)
    return GrantPaths(grants_dir=grants_dir, revoked_file=revoked_file)


@dataclass(frozen=True)
class PreauthGrant:
    """Signed preauthorization capability grant."""

    payload: dict[str, Any]

    @property
    def grant_id(self) -> str:
        """Return grant id."""
        return str(self.payload["grant_id"])

    def expires_at(self) -> datetime | None:
        """Return parsed expiry timestamp, if available."""
        raw = self.payload.get("expires_at")
        if not isinstance(raw, str):
            return None
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None

    def is_expired(self, *, now: datetime | None = None) -> bool:
        """Return whether the grant is expired as of the provided time."""
        expiry = self.expires_at()
        if expiry is None:
            return True
        current = now or datetime.now(tz=UTC)
        return current >= expiry

    def to_dict(self) -> dict[str, Any]:
        """Return serialized grant payload."""
        return dict(self.payload)


def create_grant(
    *,
    issuer: str,
    scope: dict[str, Any],
    capabilities: dict[str, bool],
    required_gates: dict[str, Any],
    budgets: dict[str, int],
    telemetry: dict[str, Any],
    expires_in_hours: int,
    break_glass: bool,
    private_key: Ed25519PrivateKey,
) -> PreauthGrant:
    """Create and sign a preauthorization grant."""
    if expires_in_hours <= 0:
        raise ValueError("expires_in_hours must be greater than zero.")
    issued_at = datetime.now(tz=UTC)
    expires_at = issued_at + timedelta(hours=expires_in_hours)
    if break_glass and expires_in_hours > 2:
        raise ValueError("Break-glass grant expiry must be <= 2 hours.")

    payload: dict[str, Any] = {
        "grant_id": str(uuid.uuid4()),
        "issued_at": issued_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "issuer": issuer.strip() or "operator",
        "scope": scope,
        "capabilities": capabilities,
        "required_gates": required_gates,
        "budgets": budgets,
        "telemetry": telemetry,
        "break_glass": break_glass,
    }
    payload["signature"] = sign_grant_payload(payload, private_key)
    return PreauthGrant(payload=payload)


def save_grant(grant: PreauthGrant, home_dir: Path | None = None) -> Path:
    """Persist signed grant under grants directory."""
    paths = resolve_grant_paths(home_dir)
    output_path = paths.grants_dir / f"{grant.grant_id}.json"
    output_path.write_text(json.dumps(grant.to_dict(), indent=2), encoding="utf-8")
    return output_path


def load_grant(grant_id: str, home_dir: Path | None = None) -> PreauthGrant | None:
    """Load one grant by id from disk."""
    paths = resolve_grant_paths(home_dir)
    candidate = paths.grants_dir / f"{grant_id}.json"
    if not candidate.exists() or not candidate.is_file():
        return None
    payload = json.loads(candidate.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    return PreauthGrant(payload=payload)


def list_grants(home_dir: Path | None = None) -> list[PreauthGrant]:
    """List all grants sorted by id."""
    paths = resolve_grant_paths(home_dir)
    grants: list[PreauthGrant] = []
    for candidate in sorted(paths.grants_dir.glob("*.json")):
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            grants.append(PreauthGrant(payload=payload))
    return grants


def revoke_grant(grant_id: str, home_dir: Path | None = None, *, reason: str = "revoked") -> None:
    """Record grant revocation in append-only revocation ledger."""
    paths = resolve_grant_paths(home_dir)
    entry = {
        "grant_id": grant_id,
        "revoked_at": datetime.now(tz=UTC).isoformat(),
        "reason": reason,
    }
    with paths.revoked_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=True))
        handle.write("\n")


def load_revoked_ids(home_dir: Path | None = None) -> set[str]:
    """Load revoked grant ids from revocation ledger."""
    paths = resolve_grant_paths(home_dir)
    if not paths.revoked_file.exists() or not paths.revoked_file.is_file():
        return set()
    revoked: set[str] = set()
    for line in paths.revoked_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("grant_id"), str):
            revoked.add(payload["grant_id"])
    return revoked


def sign_grant_payload(payload: dict[str, Any], private_key: Ed25519PrivateKey) -> dict[str, str]:
    """Sign canonicalized grant payload and return signature object."""
    canonical = _canonical_payload(payload)
    signature = private_key.sign(canonical)
    return {
        "algorithm": "ed25519",
        "value": base64.b64encode(signature).decode("ascii"),
    }


def verify_grant_signature(grant: PreauthGrant, public_keys: list[Ed25519PublicKey]) -> bool:
    """Verify grant signature against available public keys."""
    signature_obj = grant.payload.get("signature")
    if not isinstance(signature_obj, dict):
        return False
    if signature_obj.get("algorithm") != "ed25519":
        return False
    signature_raw = signature_obj.get("value")
    if not isinstance(signature_raw, str):
        return False
    try:
        signature = base64.b64decode(signature_raw.encode("ascii"))
    except ValueError:
        return False
    canonical = _canonical_payload(grant.payload)
    for key in public_keys:
        try:
            key.verify(signature, canonical)
            return True
        except InvalidSignature:
            continue
    return False


def _canonical_payload(payload: dict[str, Any]) -> bytes:
    """Canonicalize payload excluding signature for signing/verification."""
    data = {key: value for key, value in payload.items() if key != "signature"}
    serialized = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return serialized.encode("utf-8")


def ensure_project_grant_reference(project_dir: Path, grant_id: str) -> Path:
    """Write project-local grant reference file without embedding secrets."""
    reference_path = project_dir / ".autosd" / "preauth_grant_ref.json"
    reference_path.parent.mkdir(parents=True, exist_ok=True)
    keys = key_paths()
    payload = {
        "grant_id": grant_id,
        "grants_dir": str(resolve_grant_paths().grants_dir),
        "public_key_path": str(keys.public_key_path),
    }
    reference_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return reference_path
