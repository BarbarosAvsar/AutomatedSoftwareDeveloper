"""Quality and secure coding gate utilities for generated projects."""

from __future__ import annotations

import ast
import hashlib
import importlib.metadata
import importlib.util
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from automated_software_developer.agent.models import CommandResult


@dataclass(frozen=True)
class QualityGatePlan:
    """Executable quality gate command plan for a workspace."""

    format_commands: list[str]
    verification_commands: list[str]
    warnings: list[str]


@dataclass(frozen=True)
class QualityGateResult:
    """Static quality gate findings that are not command-based."""

    docstring_violations: list[str]
    syntax_errors: list[str]

    @property
    def passed(self) -> bool:
        """Return whether quality checks have no findings."""
        return not self.docstring_violations and not self.syntax_errors


@dataclass(frozen=True)
class QualityGateCacheEntry:
    """Cached results for quality gate command execution."""

    fingerprint: str
    commands: list[str]
    results: list[CommandResult]

    def to_dict(self) -> dict[str, Any]:
        """Serialize cache entry for persistence."""
        return {
            "version": 1,
            "fingerprint": self.fingerprint,
            "commands": list(self.commands),
            "results": [_serialize_command_result(item) for item in self.results],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> QualityGateCacheEntry | None:
        """Deserialize cache entry when payload is valid."""
        if payload.get("version") != 1:
            return None
        fingerprint = payload.get("fingerprint")
        commands = payload.get("commands")
        results = payload.get("results")
        if not isinstance(fingerprint, str) or not isinstance(commands, list):
            return None
        if not isinstance(results, list):
            return None
        parsed_results: list[CommandResult] = []
        for item in results:
            if not isinstance(item, dict):
                return None
            parsed = _deserialize_command_result(item)
            if parsed is None:
                return None
            parsed_results.append(parsed)
        return cls(fingerprint=fingerprint, commands=commands, results=parsed_results)


def build_quality_gate_plan(
    workspace_dir: Path,
    *,
    enforce_quality_gates: bool,
    enable_security_scan: bool,
    security_scan_mode: str,
) -> QualityGatePlan:
    """Build a deterministic quality gate command plan for the workspace."""
    if not enforce_quality_gates:
        return QualityGatePlan(format_commands=[], verification_commands=[], warnings=[])

    warnings: list[str] = []
    format_commands: list[str] = []
    verification_commands: list[str] = [_readme_exists_command()]
    has_python_files = any(
        path.suffix == ".py" and ".autosd" not in path.parts
        for path in workspace_dir.rglob("*.py")
    )
    if not has_python_files:
        return QualityGatePlan(
            format_commands=format_commands,
            verification_commands=verification_commands,
            warnings=warnings,
        )

    verification_commands.insert(0, "python -m compileall -q .")

    if _module_available("ruff"):
        format_commands.append("python -m ruff format .")
        verification_commands.append("python -m ruff check .")
    else:
        warnings.append("ruff is not available; skipping Python lint/format gate.")

    if _module_available("mypy") and _has_mypy_config(workspace_dir):
        verification_commands.append("python -m mypy .")
    elif _has_mypy_config(workspace_dir):
        warnings.append("mypy config detected but mypy is not installed; skipping type gate.")

    scan_enabled = enable_security_scan and security_scan_mode != "off"
    if scan_enabled:
        if _module_available("bandit"):
            verification_commands.append(
                "python -m bandit -q -r . -x "
                "tests,./tests,.venv,./.venv,venv,./venv,.git,./.git,.autosd,./.autosd"
            )
        elif security_scan_mode == "required":
            raise RuntimeError("Security scan mode is 'required' but bandit is not installed.")
        else:
            warnings.append("bandit is not available; skipping optional security scan.")

    return QualityGatePlan(
        format_commands=_dedupe(format_commands),
        verification_commands=_dedupe(verification_commands),
        warnings=warnings,
    )


def evaluate_python_quality(
    workspace_dir: Path,
    *,
    enforce_docstrings: bool,
) -> QualityGateResult:
    """Run static Python-specific checks for syntax and docstring coverage."""
    syntax_errors: list[str] = []
    docstring_violations: list[str] = []
    python_files = [
        path for path in workspace_dir.rglob("*.py") if ".autosd" not in path.parts
    ]
    for path in python_files:
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            syntax_errors.append(f"{path}:unable to read file")
            continue
        try:
            tree = ast.parse(content)
        except SyntaxError as exc:
            syntax_errors.append(f"{path}:{exc.lineno}:{exc.msg}")
            continue
        if enforce_docstrings and _should_enforce_docstrings(path):
            docstring_violations.extend(_collect_missing_docstrings(path, tree))
    return QualityGateResult(
        docstring_violations=docstring_violations,
        syntax_errors=syntax_errors,
    )


def load_quality_gate_cache(workspace_dir: Path) -> QualityGateCacheEntry | None:
    """Load cached quality gate results when available."""
    cache_path = _quality_cache_path(workspace_dir)
    if not cache_path.exists():
        return None
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(payload, dict):
        return None
    return QualityGateCacheEntry.from_dict(payload)


def save_quality_gate_cache(workspace_dir: Path, entry: QualityGateCacheEntry) -> None:
    """Persist quality gate cache entry to disk."""
    cache_path = _quality_cache_path(workspace_dir)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(entry.to_dict(), indent=2), encoding="utf-8")


def compute_quality_gate_fingerprint(
    workspace_dir: Path,
    *,
    commands: list[str],
    config: dict[str, Any],
) -> str:
    """Compute deterministic fingerprint for quality gate caching."""
    hasher = hashlib.sha256()
    metadata = {
        "commands": commands,
        "config": config,
        "tool_versions": quality_tool_versions(),
    }
    hasher.update(json.dumps(metadata, sort_keys=True).encode("utf-8"))
    for path in _iter_cacheable_files(workspace_dir):
        relative = path.relative_to(workspace_dir).as_posix()
        hasher.update(relative.encode("utf-8"))
        try:
            data = path.read_bytes()
        except OSError:
            continue
        hasher.update(data)
    return hasher.hexdigest()


def quality_tool_versions() -> dict[str, str]:
    """Return installed tool versions relevant to quality gates."""
    versions: dict[str, str] = {}
    for package in ("ruff", "mypy", "pytest", "bandit"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "not-installed"
    return versions


def _should_enforce_docstrings(path: Path) -> bool:
    """Return whether docstring coverage should be enforced for a Python file."""
    relative = str(path).replace("\\", "/").lower()
    return "/tests/" not in f"/{relative}" and not relative.endswith("/conftest.py")


def _collect_missing_docstrings(path: Path, tree: ast.AST) -> list[str]:
    """Collect missing docstring locations for public module/class members."""
    violations: list[str] = []
    module = tree if isinstance(tree, ast.Module) else ast.Module(body=[], type_ignores=[])
    for node in module.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if node.name.startswith("_"):
                continue
            if ast.get_docstring(node) is None:
                violations.append(f"{path}:{node.lineno}:{node.name}")
        if isinstance(node, ast.ClassDef):
            if ast.get_docstring(node) is None:
                violations.append(f"{path}:{node.lineno}:{node.name}")
            for child in node.body:
                if not isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                    continue
                if child.name.startswith("_"):
                    continue
                if ast.get_docstring(child) is None:
                    violations.append(f"{path}:{child.lineno}:{node.name}.{child.name}")
    return violations


def _has_mypy_config(workspace_dir: Path) -> bool:
    """Return whether mypy configuration appears present in workspace."""
    mypy_ini = workspace_dir / "mypy.ini"
    if mypy_ini.exists():
        return True

    setup_cfg = workspace_dir / "setup.cfg"
    if setup_cfg.exists():
        content = setup_cfg.read_text(encoding="utf-8", errors="ignore")
        if "[mypy" in content.lower():
            return True

    pyproject = workspace_dir / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text(encoding="utf-8", errors="ignore")
        if "[tool.mypy]" in content.lower():
            return True
    return False


def _module_available(module_name: str) -> bool:
    """Return whether a Python module can be imported in current runtime."""
    return importlib.util.find_spec(module_name) is not None


def _readme_exists_command() -> str:
    """Return command asserting README presence for generated project docs."""
    return "python -c \"from pathlib import Path; assert Path('README.md').exists()\""


def _dedupe(items: list[str]) -> list[str]:
    """Return unique list preserving item order."""
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output


def _quality_cache_path(workspace_dir: Path) -> Path:
    """Return path for quality gate cache file."""
    return workspace_dir / ".autosd" / "provenance" / "quality_gate_cache.json"


def _iter_cacheable_files(workspace_dir: Path) -> list[Path]:
    """Return a deterministic list of files included in cache fingerprint."""
    skip_dirs = {
        ".autosd",
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
    }
    files: list[Path] = []
    for path in workspace_dir.rglob("*"):
        if not path.is_file():
            continue
        if skip_dirs.intersection(path.parts):
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.as_posix())


def _serialize_command_result(result: CommandResult) -> dict[str, Any]:
    """Serialize command results with trimmed outputs."""
    return {
        "command": result.command,
        "exit_code": result.exit_code,
        "stdout": _truncate_output(result.stdout),
        "stderr": _truncate_output(result.stderr),
        "duration_seconds": result.duration_seconds,
    }


def _deserialize_command_result(payload: dict[str, Any]) -> CommandResult | None:
    """Deserialize command result payload when valid."""
    command = payload.get("command")
    exit_code = payload.get("exit_code")
    stdout = payload.get("stdout")
    stderr = payload.get("stderr")
    duration = payload.get("duration_seconds")
    if not isinstance(command, str):
        return None
    if not isinstance(exit_code, int):
        return None
    if not isinstance(stdout, str) or not isinstance(stderr, str):
        return None
    if not isinstance(duration, int | float):
        return None
    return CommandResult(
        command=command,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=float(duration),
    )


def _truncate_output(value: str, limit: int = 2000) -> str:
    """Trim captured output to a bounded length."""
    if len(value) <= limit:
        return value
    return value[-limit:]
