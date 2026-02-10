"""Workspace management with path safety guarantees."""

from __future__ import annotations

import os
from pathlib import Path

from automated_software_developer.agent.security import SecurityError, ensure_safe_relative_path


class FileWorkspace:
    """Abstraction around project file mutations within a bounded directory."""

    def __init__(self, base_dir: Path) -> None:
        """Initialize workspace rooted at base_dir."""
        self.base_dir = base_dir
        self.changed_files: set[str] = set()

    def ensure_exists(self) -> None:
        """Create the workspace root directory if it does not exist."""
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def write_file(self, relative_path: str, content: str) -> None:
        """Write UTF-8 file content under workspace root."""
        target = ensure_safe_relative_path(self.base_dir, relative_path)
        root = self.base_dir.resolve()
        if target.is_dir():
            raise SecurityError(f"Cannot write file over directory: {relative_path}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        self.changed_files.add(str(target.relative_to(root)).replace("\\", "/"))

    def delete_file(self, relative_path: str) -> None:
        """Delete a file under workspace root if present."""
        target = ensure_safe_relative_path(self.base_dir, relative_path)
        root = self.base_dir.resolve()
        if target.exists() and target.is_file():
            target.unlink()
            self.changed_files.add(str(target.relative_to(root)).replace("\\", "/"))

    def read_file(self, relative_path: str) -> str:
        """Read a UTF-8 text file under workspace root."""
        target = ensure_safe_relative_path(self.base_dir, relative_path)
        return target.read_text(encoding="utf-8")

    def read_optional(self, relative_path: str) -> str | None:
        """Read a UTF-8 text file if it exists."""
        target = ensure_safe_relative_path(self.base_dir, relative_path)
        if not target.exists() or not target.is_file():
            return None
        return target.read_text(encoding="utf-8")

    def set_executable(self, relative_path: str) -> None:
        """Ensure a file under workspace root is marked executable."""
        target = ensure_safe_relative_path(self.base_dir, relative_path)
        if not target.exists() or not target.is_file():
            raise SecurityError(f"Cannot mark missing file executable: {relative_path}")
        mode = target.stat().st_mode
        target.chmod(mode | 0o111)

    def list_files(self, max_files: int = 500) -> list[str]:
        """Return a deterministic list of relative paths for non-hidden files."""
        skip_dirs = {
            ".autosd",
            ".git",
            ".venv",
            "venv",
            "node_modules",
            "__pycache__",
        }
        files: list[str] = []
        base = self.base_dir
        for root, dirnames, filenames in os.walk(base):
            if len(files) >= max_files:
                break
            dirnames[:] = sorted(name for name in dirnames if name not in skip_dirs)
            for filename in sorted(filenames):
                if len(files) >= max_files:
                    break
                path = Path(root) / filename
                relative = path.relative_to(base)
                files.append(str(relative).replace("\\", "/"))
        return files

    def build_context_snapshot(self, max_files: int = 40, max_chars_per_file: int = 3000) -> str:
        """Create a compact textual snapshot for prompting the coding model."""
        sections: list[str] = []
        for relative_path in self.list_files(max_files=max_files):
            path = self.base_dir / relative_path
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            clipped = text[:max_chars_per_file]
            if len(text) > max_chars_per_file:
                clipped += "\n...<truncated>..."
            sections.append(f"### FILE: {relative_path}\n{clipped}\n")
        return "\n".join(sections)
