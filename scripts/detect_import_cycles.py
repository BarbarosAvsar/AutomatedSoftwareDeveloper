"""Detect local import cycles in automated_software_developer package."""

from __future__ import annotations

import ast
from pathlib import Path

PKG = "automated_software_developer"


def module_name(root: Path, path: Path) -> str:
    rel = path.relative_to(root).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join([PKG, *parts]) if parts else PKG


def build_graph(root: Path) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    files = sorted(root.rglob("*.py"))
    modules = {module_name(root, p) for p in files}
    for path in files:
        src = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(src)
        mod = module_name(root, path)
        graph.setdefault(mod, set())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    if name.startswith(PKG):
                        graph[mod].add(name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.level == 0 and node.module.startswith(PKG):
                    graph[mod].add(node.module)
                elif node.level > 0:
                    prefix = mod.split(".")[:-node.level]
                    absolute = ".".join(prefix + [node.module]) if node.module else ".".join(prefix)
                    if absolute.startswith(PKG):
                        graph[mod].add(absolute)
        graph[mod] = {dep for dep in graph[mod] if dep in modules}
    return graph


def find_cycle(graph: dict[str, set[str]]) -> list[str] | None:
    seen: set[str] = set()
    stack: list[str] = []
    in_stack: set[str] = set()

    def dfs(node: str) -> list[str] | None:
        seen.add(node)
        stack.append(node)
        in_stack.add(node)
        for nxt in graph.get(node, set()):
            if nxt not in seen:
                cycle = dfs(nxt)
                if cycle:
                    return cycle
            elif nxt in in_stack:
                idx = stack.index(nxt)
                return stack[idx:] + [nxt]
        stack.pop()
        in_stack.remove(node)
        return None

    for node in graph:
        if node not in seen:
            cycle = dfs(node)
            if cycle:
                return cycle
    return None


def main() -> None:
    root = Path(PKG)
    graph = build_graph(root)
    cycle = find_cycle(graph)
    if cycle:
        raise SystemExit(f"Import cycle detected: {' -> '.join(cycle)}")
    print("No import cycles detected.")


if __name__ == "__main__":
    main()
