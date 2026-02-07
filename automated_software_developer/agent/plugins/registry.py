"""Plugin registry for enable/disable management."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from automated_software_developer.agent.plugins.loader import discover_plugins


@dataclass(frozen=True)
class PluginInfo:
    """Serialized plugin info."""

    plugin_id: str
    name: str
    enabled: bool


class PluginRegistry:
    """Manage plugin enable/disable state."""

    def __init__(self, *, registry_path: Path | None = None) -> None:
        self._registry_path = registry_path or Path.home() / ".autosd" / "plugins" / "registry.json"
        self._registry_path.parent.mkdir(parents=True, exist_ok=True)

    def list_plugins(self) -> list[PluginInfo]:
        """List discovered plugins with enabled status."""
        enabled = self._load_enabled()
        plugins = []
        for descriptor in discover_plugins():
            plugins.append(
                PluginInfo(
                    plugin_id=descriptor.plugin_id,
                    name=descriptor.name,
                    enabled=descriptor.plugin_id in enabled,
                )
            )
        return plugins

    def enable_plugin(self, plugin_id: str) -> PluginInfo:
        """Enable a plugin by id."""
        plugins = {plugin.plugin_id: plugin for plugin in self.list_plugins()}
        if plugin_id not in plugins:
            raise ValueError("Unknown plugin id.")
        enabled = self._load_enabled()
        enabled.add(plugin_id)
        self._save_enabled(enabled)
        plugin = plugins[plugin_id]
        return PluginInfo(plugin_id=plugin.plugin_id, name=plugin.name, enabled=True)

    def disable_plugin(self, plugin_id: str) -> PluginInfo:
        """Disable a plugin by id."""
        plugins = {plugin.plugin_id: plugin for plugin in self.list_plugins()}
        if plugin_id not in plugins:
            raise ValueError("Unknown plugin id.")
        enabled = self._load_enabled()
        enabled.discard(plugin_id)
        self._save_enabled(enabled)
        plugin = plugins[plugin_id]
        return PluginInfo(plugin_id=plugin.plugin_id, name=plugin.name, enabled=False)

    def _load_enabled(self) -> set[str]:
        if not self._registry_path.exists():
            return set()
        payload = json.loads(self._registry_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("Plugin registry must be a JSON list.")
        return {str(item) for item in payload}

    def _save_enabled(self, enabled: set[str]) -> None:
        self._registry_path.write_text(
            json.dumps(sorted(enabled), indent=2),
            encoding="utf-8",
        )
