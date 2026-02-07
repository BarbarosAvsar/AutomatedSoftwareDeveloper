"""Local asymmetric key management for preauthorization grants."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

AUTOSD_PREAUTH_HOME_ENV = "AUTOSD_PREAUTH_HOME"


@dataclass(frozen=True)
class KeyPaths:
    """Filesystem locations for active preauth key material."""

    home_dir: Path
    private_key_path: Path
    public_key_path: Path


def resolve_preauth_home() -> Path:
    """Resolve preauth home directory from env or default location."""
    env_value = os.environ.get(AUTOSD_PREAUTH_HOME_ENV)
    if env_value:
        return Path(env_value).expanduser().resolve()
    return (Path.home() / ".autosd" / "preauth").resolve()


def key_paths(home_dir: Path | None = None) -> KeyPaths:
    """Return active key paths under preauth home."""
    resolved_home = (home_dir or resolve_preauth_home()).expanduser().resolve()
    keys_dir = resolved_home / "keys"
    return KeyPaths(
        home_dir=resolved_home,
        private_key_path=keys_dir / "private_key.pem",
        public_key_path=keys_dir / "public_key.pem",
    )


def init_keys(home_dir: Path | None = None, *, force: bool = False) -> KeyPaths:
    """Initialize Ed25519 key pair on local filesystem."""
    paths = key_paths(home_dir)
    paths.private_key_path.parent.mkdir(parents=True, exist_ok=True)
    if not force and paths.private_key_path.exists() and paths.public_key_path.exists():
        return paths

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    paths.private_key_path.write_bytes(private_bytes)
    paths.public_key_path.write_bytes(public_bytes)
    _set_private_permissions(paths.private_key_path)
    return paths


def rotate_keys(home_dir: Path | None = None) -> KeyPaths:
    """Rotate key pair and archive previous public key for verification history."""
    paths = key_paths(home_dir)
    if paths.public_key_path.exists():
        archive_dir = paths.public_key_path.parent / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(tz=UTC).strftime("%Y%m%d%H%M%S")
        archive_path = archive_dir / f"public_key_{stamp}.pem"
        archive_path.write_bytes(paths.public_key_path.read_bytes())
    return init_keys(home_dir=paths.home_dir, force=True)


def load_private_key(home_dir: Path | None = None) -> Ed25519PrivateKey:
    """Load active private key for signing grants."""
    paths = key_paths(home_dir)
    if not paths.private_key_path.exists():
        raise FileNotFoundError("Preauth private key not found. Run 'autosd preauth init-keys'.")
    raw = paths.private_key_path.read_bytes()
    key = serialization.load_pem_private_key(raw, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("Unsupported private key type; expected Ed25519.")
    return key


def load_public_keys(home_dir: Path | None = None) -> list[Ed25519PublicKey]:
    """Load active and archived public keys for signature verification."""
    paths = key_paths(home_dir)
    candidates: list[Path] = []
    if paths.public_key_path.exists():
        candidates.append(paths.public_key_path)
    archive_dir = paths.public_key_path.parent / "archive"
    if archive_dir.exists():
        candidates.extend(sorted(archive_dir.glob("public_key_*.pem")))

    keys: list[Ed25519PublicKey] = []
    for candidate in candidates:
        raw = candidate.read_bytes()
        key = serialization.load_pem_public_key(raw)
        if isinstance(key, Ed25519PublicKey):
            keys.append(key)
    return keys


def _set_private_permissions(path: Path) -> None:
    """Set restrictive permissions for private key when supported."""
    try:
        os.chmod(path, 0o600)
    except OSError:
        return
