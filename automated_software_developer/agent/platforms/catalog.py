"""Platform adapter catalog and selection helpers."""

from __future__ import annotations

from pathlib import Path

from automated_software_developer.agent.models import RefinedRequirements
from automated_software_developer.agent.platforms.api_service import APIServiceAdapter
from automated_software_developer.agent.platforms.base import (
    CapabilityGraph,
    PlatformAdapter,
    PlatformPlan,
)
from automated_software_developer.agent.platforms.cli_tool import CLIToolAdapter
from automated_software_developer.agent.platforms.scaffold_only import (
    DesktopAppAdapter,
    MobileAppAdapter,
)
from automated_software_developer.agent.platforms.web_app import WebAppAdapter


def adapter_catalog() -> dict[str, PlatformAdapter]:
    """Return deterministic adapter catalog keyed by adapter id."""
    adapters: list[PlatformAdapter] = [
        APIServiceAdapter(),
        WebAppAdapter(),
        CLIToolAdapter(),
        DesktopAppAdapter(),
        MobileAppAdapter(),
    ]
    return {adapter.adapter_id: adapter for adapter in adapters}


def select_platform_adapter(
    refined: RefinedRequirements,
    *,
    project_dir: Path,
    preferred_adapter: str | None = None,
) -> PlatformPlan:
    """Select best adapter from catalog and build platform plan."""
    catalog = adapter_catalog()
    if preferred_adapter is not None:
        adapter = catalog.get(preferred_adapter)
        if adapter is None:
            allowed = ", ".join(sorted(catalog))
            raise ValueError(f"Unknown preferred adapter '{preferred_adapter}'. Allowed: {allowed}")
        return adapter.build_plan(refined, project_dir)

    ranked = sorted(
        catalog.values(),
        key=lambda item: item.score(refined),
        reverse=True,
    )
    selected = ranked[0]
    return selected.build_plan(refined, project_dir)


def build_capability_graph() -> CapabilityGraph:
    """Build capability graph from registered adapter metadata."""
    adapters = adapter_catalog()
    payload: dict[str, dict[str, object]] = {}
    for adapter_id, adapter in adapters.items():
        payload[adapter_id] = {
            "description": adapter.description,
            "supported_deploy_targets": adapter.supported_deploy_targets(),
            "minimum_test_patterns": adapter.minimum_test_patterns(),
            "telemetry_hooks": adapter.telemetry_hooks(),
        }
    return CapabilityGraph(adapters=payload)
