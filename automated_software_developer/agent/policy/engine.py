"""Policy-as-code resolution and action gating helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from automated_software_developer.agent.preauth.grants import PreauthGrant
from automated_software_developer.agent.preauth.verify import capability_allowed

POLICY_SNAPSHOT_SCHEMA: dict[str, Any] = {
    "title": "PolicySnapshot",
    "type": "object",
    "required": [
        "telemetry",
        "deployment",
        "gitops",
        "app_store",
        "credentials",
        "budgets",
    ],
}

DEFAULT_BASE_POLICY: dict[str, Any] = {
    "telemetry": {
        "mode": "off",
        "retention_days": 30,
    },
    "deployment": {
        "allow_dev": True,
        "allow_staging": True,
        "allow_prod": False,
        "require_canary_for_prod": True,
    },
    "gitops": {
        "auto_merge": False,
        "auto_push": False,
    },
    "app_store": {
        "publish_enabled": False,
    },
    "credentials": {
        "require_preprovisioned": True,
    },
    "budgets": {
        "max_deploys_per_day": 20,
        "max_patches_per_incident": 3,
        "max_auto_merges_per_day": 10,
        "max_failures_before_halt": 5,
    },
}


@dataclass(frozen=True)
class PolicyDecision:
    """Decision result for one gated action."""

    allowed: bool
    reason: str


@dataclass(frozen=True)
class EffectivePolicy:
    """Resolved policy snapshot after merging sources and grant allowlist."""

    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Return serialized policy snapshot."""
        return dict(self.payload)


def resolve_effective_policy(
    *,
    project_policy: dict[str, Any] | None,
    grant: PreauthGrant | None,
) -> EffectivePolicy:
    """Resolve base + project policy and constrain using grant capabilities."""
    merged = _deep_merge(DEFAULT_BASE_POLICY, project_policy or {})
    if grant is None:
        return EffectivePolicy(payload=merged)

    deployment = dict(merged.get("deployment", {}))
    deployment["allow_dev"] = bool(deployment.get("allow_dev", True)) and capability_allowed(
        grant,
        "auto_deploy_dev",
    )
    deployment["allow_staging"] = bool(deployment.get("allow_staging", True)) and (
        capability_allowed(
            grant,
            "auto_deploy_staging",
        )
    )
    deployment["allow_prod"] = capability_allowed(grant, "auto_deploy_prod")

    gitops = dict(merged.get("gitops", {}))
    gitops["auto_push"] = gitops.get("auto_push", False) and capability_allowed(grant, "auto_push")
    gitops["auto_merge"] = gitops.get("auto_merge", False) and capability_allowed(
        grant,
        "auto_merge_pr",
    )

    app_store = dict(merged.get("app_store", {}))
    app_store["publish_enabled"] = app_store.get("publish_enabled", False) and capability_allowed(
        grant,
        "publish_app_store",
    )

    merged["deployment"] = deployment
    merged["gitops"] = gitops
    merged["app_store"] = app_store
    merged["grant_id"] = grant.grant_id
    return EffectivePolicy(payload=merged)


def evaluate_action(
    *,
    policy: EffectivePolicy,
    action: str,
    environment: str | None = None,
) -> PolicyDecision:
    """Return policy decision for action and optional environment."""
    payload = policy.payload
    deployment = payload.get("deployment", {})
    gitops = payload.get("gitops", {})
    app_store = payload.get("app_store", {})

    if action == "deploy":
        env = (environment or "dev").lower()
        if env == "prod" and not bool(deployment.get("allow_prod", False)):
            return PolicyDecision(False, "prod_deploy_blocked")
        if env == "staging" and not bool(deployment.get("allow_staging", True)):
            return PolicyDecision(False, "staging_deploy_blocked")
        if env == "dev" and not bool(deployment.get("allow_dev", True)):
            return PolicyDecision(False, "dev_deploy_blocked")
        return PolicyDecision(True, "ok")

    if action == "auto_push":
        if not bool(gitops.get("auto_push", False)):
            return PolicyDecision(False, "auto_push_blocked")
        return PolicyDecision(True, "ok")

    if action == "auto_merge":
        if not bool(gitops.get("auto_merge", False)):
            return PolicyDecision(False, "auto_merge_blocked")
        return PolicyDecision(True, "ok")

    if action == "publish_app_store":
        if not bool(app_store.get("publish_enabled", False)):
            return PolicyDecision(False, "app_store_blocked")
        return PolicyDecision(True, "ok")

    return PolicyDecision(False, "unknown_action")


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries without mutating inputs."""
    output: dict[str, Any] = {}
    keys = set(base) | set(override)
    for key in keys:
        base_value = base.get(key)
        override_value = override.get(key)
        if isinstance(base_value, dict) and isinstance(override_value, dict):
            output[key] = _deep_merge(base_value, override_value)
        elif override_value is not None:
            output[key] = override_value
        else:
            output[key] = base_value
    return output
