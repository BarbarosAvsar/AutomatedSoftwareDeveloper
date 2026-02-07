from pathlib import Path

from automated_software_developer.agent.plugins.registry import PluginRegistry


def test_plugin_registry_enable_disable(monkeypatch: object, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    plugin_dir = tmp_path / ".autosd" / "plugins"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "hello_world.py").write_text("# plugin", encoding="utf-8")

    registry = PluginRegistry()
    plugins = registry.list_plugins()
    assert plugins
    plugin_id = plugins[0].plugin_id

    enabled = registry.enable_plugin(plugin_id)
    assert enabled.enabled is True

    disabled = registry.disable_plugin(plugin_id)
    assert disabled.enabled is False
