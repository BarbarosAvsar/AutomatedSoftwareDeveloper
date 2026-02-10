"""Security helpers for filesystem and command safety."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final


class SecurityError(RuntimeError):
    """Raised when an unsafe operation is detected."""


DANGEROUS_COMMAND_PATTERNS = (
    r"\brm\s+-rf\s+[/\\]",
    r"\brm\s+-rf\s+\.\.",
    r"\bdel\s+/s\b",
    r"\bformat\s+[a-z]:",
    r"\bmkfs\b",
    r"\bshutdown\b",
    r"\bpoweroff\b",
    r"remove-item\s+.+-recurse.+-force",
)

POTENTIAL_SECRET_PATTERNS: tuple[tuple[str, str], ...] = (
    ("openai_api_key", r"sk-[A-Za-z0-9]{20,}"),
    ("github_token", r"gh[pousr]_[A-Za-z0-9]{20,}"),
    ("aws_access_key_id", r"AKIA[0-9A-Z]{16}"),
    ("private_key_block", r"-----BEGIN (?:RSA|OPENSSH|PRIVATE) KEY-----"),
    ("jwt_token", r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),
    ("bearer_token", r"(?i)bearer\s+[A-Za-z0-9._-]{16,}"),
)

SENSITIVE_KEYWORDS: Final[tuple[str, ...]] = (
    "token",
    "secret",
    "password",
    "api_key",
    "apikey",
    "private_key",
    "access_key",
)

SENSITIVE_KEY_PATTERN: Final[str] = (
    r"[A-Za-z0-9_.-]*(?:token|secret|api[_-]?key|password|passphrase|"
    r"private[_-]?key|access[_-]?key)[A-Za-z0-9_.-]*"
)

_SENSITIVE_INLINE_VALUE_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"(?i)(\b{SENSITIVE_KEY_PATTERN}\b)(\s*[:=]\s*)([^\s,;]+)"
)
_SENSITIVE_QUOTED_VALUE_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"(?i)(\b{SENSITIVE_KEY_PATTERN}\b)(\s*[:=]\s*)(\"[^\"]*\"|'[^']*')"
)
_SENSITIVE_QUERY_PARAM_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"(?i)([?&]{SENSITIVE_KEY_PATTERN}=)[^&#\s]+"
)
_BASIC_AUTH_HEADER_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?i)(authorization\s*:\s*basic\s+)[A-Za-z0-9+/=]+"
)
_X_API_KEY_HEADER_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?i)(x-api-key\s*:\s*)[^\s]+"
)


def ensure_safe_relative_path(base_dir: Path, relative_path: str) -> Path:
    """Resolve and validate that relative_path stays within base_dir."""
    target = (base_dir / relative_path).resolve()
    root = base_dir.resolve()
    if target == root:
        raise SecurityError("Target path must reference a file, not the workspace root.")
    if root not in target.parents:
        raise SecurityError(f"Unsafe path traversal attempt: {relative_path}")
    return target


def is_command_safe(command: str) -> bool:
    """Return False if command appears destructive."""
    lowered = command.strip().lower()
    if not lowered:
        return False
    return not any(re.search(pattern, lowered) for pattern in DANGEROUS_COMMAND_PATTERNS)


def find_potential_secrets(text: str) -> list[str]:
    """Return labels for secret-like substrings found in text."""
    findings: list[str] = []
    for label, pattern in POTENTIAL_SECRET_PATTERNS:
        if re.search(pattern, text):
            findings.append(label)
    return findings


def scan_workspace_for_secrets(base_dir: Path) -> list[str]:
    """Scan text files for secret-like patterns and return finding strings."""
    findings: list[str] = []
    for path in base_dir.rglob("*"):
        if not path.is_file():
            continue
        if ".git" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for label in find_potential_secrets(text):
            findings.append(f"{path.relative_to(base_dir)}:{label}")
    return findings


def is_probably_sensitive_key(key: str) -> bool:
    """Return whether a dictionary key likely contains sensitive material."""
    lowered = key.lower()
    return any(keyword in lowered for keyword in SENSITIVE_KEYWORDS)


def _redact_sensitive_key_value_pairs(text: str) -> str:
    """Redact sensitive key-value patterns while preserving delimiter formatting."""

    def _replace_match(match: re.Match[str]) -> str:
        return f"{match.group(1)}{match.group(2)}[REDACTED:value]"

    redacted = _SENSITIVE_INLINE_VALUE_PATTERN.sub(_replace_match, text)
    redacted = _SENSITIVE_QUOTED_VALUE_PATTERN.sub(_replace_match, redacted)
    redacted = _SENSITIVE_QUERY_PARAM_PATTERN.sub(r"\1[REDACTED:value]", redacted)
    return redacted


def redact_sensitive_text(text: str) -> str:
    """Replace secret-like values with redaction placeholders."""
    redacted = text
    for label, pattern in POTENTIAL_SECRET_PATTERNS:
        redacted = re.sub(pattern, f"[REDACTED:{label}]", redacted)

    # Redact common assignment-style secret declarations.
    redacted = re.sub(
        r"(?i)\b([A-Z0-9_]*(?:TOKEN|SECRET|API[_-]?KEY|PASSWORD)[A-Z0-9_]*)\s*=\s*['\"][^'\"]+['\"]",
        r"\1='[REDACTED:value]'",
        redacted,
    )
    redacted = re.sub(
        r"(?i)\b([A-Z0-9_]*(?:TOKEN|SECRET|API[_-]?KEY|PASSWORD)[A-Z0-9_]*)\s*:\s*['\"][^'\"]+['\"]",
        r"\1:'[REDACTED:value]'",
        redacted,
    )
    redacted = _redact_sensitive_key_value_pairs(redacted)
    redacted = _BASIC_AUTH_HEADER_PATTERN.sub(r"\1[REDACTED:value]", redacted)
    redacted = _X_API_KEY_HEADER_PATTERN.sub(r"\1[REDACTED:value]", redacted)
    redacted = re.sub(
        r"(?i)(https?://[^:\s]+:)[^@\s/]+@",
        r"\1[REDACTED:value]@",
        redacted,
    )
    return redacted
