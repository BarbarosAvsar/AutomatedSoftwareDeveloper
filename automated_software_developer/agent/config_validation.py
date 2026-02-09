"""Shared configuration validation helpers."""

from __future__ import annotations


def require_positive_int(value: int, field_name: str) -> int:
    """Validate a positive integer input and return it."""
    if value <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")
    return value


def validate_choice(value: str, field_name: str, allowed: set[str]) -> str:
    """Validate that a string value is within a set of allowed options."""
    if value not in allowed:
        options = ", ".join(sorted(allowed))
        raise ValueError(f"{field_name} must be one of: {options}.")
    return value


def validate_security_scan_mode(value: str) -> str:
    """Validate security scan mode option."""
    return validate_choice(value, "security_scan_mode", {"off", "if-available", "required"})


def validate_sbom_mode(value: str) -> str:
    """Validate SBOM mode option."""
    return validate_choice(value, "sbom_mode", {"off", "if-available", "required"})
