"""Plugin discovery utilities."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PluginDescriptor:
    """Plugin discovery result."""

    plugin_id: str
    name: str
    path: Path


def discover_plugin_paths() -> list[Path]:
    """Return search paths for plugins."""
    paths = [
        Path.home() / ".autosd" / "plugins",
        Path.cwd() / "plugins",
        Path.cwd() / "skills",
    ]
    return [path for path in paths if path.exists()]


def discover_plugins() -> list[PluginDescriptor]:
    """Discover plugin files in configured paths."""
    descriptors: list[PluginDescriptor] = []
    for directory in discover_plugin_paths():
        for path in directory.glob("*.py"):
            plugin_id = path.stem
            descriptors.append(
                PluginDescriptor(
                    plugin_id=plugin_id,
                    name=plugin_id.replace("_", " ").title(),
                    path=path,
                )
            )
    return descriptors
