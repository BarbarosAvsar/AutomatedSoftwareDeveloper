"""Privacy-safe analytics hooks scaffold."""

from __future__ import annotations


def analytics_hook_stub() -> str:
    """Return a stub snippet for analytics integration."""
    return (
        "def record_event(name: str, metadata: dict[str, str]) -> None:\n"
        "    \"\"\"Record a privacy-safe analytics event.\"\"\"\n"
        "    _ = name\n"
        "    _ = metadata\n"
        "    # Implement local-only analytics if explicitly required.\n"
    )
