"""Development agent module for orchestrator decomposition."""

from __future__ import annotations

from automated_software_developer.agent.models import ExecutionBundle


class DevAgent:
    """Represents implementation responsibilities in the orchestration loop."""

    def prepare_bundle(self, payload: dict[str, object]) -> ExecutionBundle:
        """Build execution bundle from model payload."""
        return ExecutionBundle.from_dict(payload)
