"""Department-level policy controls for autonomous organization."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DepartmentPolicy:
    """Policy knobs governing department autonomy and budgets."""

    daemon_enabled_departments: set[str] = field(default_factory=lambda: {
        "program_management",
        "engineering",
        "security",
        "operations",
        "data_intelligence",
        "support_ops",
    })
    actions_requiring_preauth: set[str] = field(
        default_factory=lambda: {"deploy_prod", "auto_merge", "publish_app_store"}
    )
    department_budgets: dict[str, int] = field(
        default_factory=lambda: {
            "engineering": 10,
            "operations": 10,
            "security": 10,
            "data_intelligence": 10,
            "support_ops": 10,
            "program_management": 10,
        }
    )
    external_learning_enabled: bool = False
    allowed_corpus_licenses: set[str] = field(default_factory=lambda: {"MIT", "Apache-2.0"})
    support_intake_sources: set[str] = field(default_factory=lambda: {"manual", "telemetry"})

    def ensure_budget(self, department: str, required: int = 1) -> None:
        """Validate that the department budget allows the requested action count."""
        budget = self.department_budgets.get(department, 0)
        if required <= 0:
            raise ValueError("required budget must be greater than zero.")
        if budget < required:
            raise ValueError(f"Budget exceeded for {department}.")

    def with_allowed_licenses(self, licenses: Iterable[str]) -> DepartmentPolicy:
        """Return a copy with updated allowed license set."""
        return DepartmentPolicy(
            daemon_enabled_departments=set(self.daemon_enabled_departments),
            actions_requiring_preauth=set(self.actions_requiring_preauth),
            department_budgets=dict(self.department_budgets),
            external_learning_enabled=self.external_learning_enabled,
            allowed_corpus_licenses=set(licenses),
            support_intake_sources=set(self.support_intake_sources),
        )
