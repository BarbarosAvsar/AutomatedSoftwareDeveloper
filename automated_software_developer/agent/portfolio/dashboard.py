"""Read-only local dashboard API exposing portfolio registry state."""

from __future__ import annotations

import json
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import unquote, urlparse

from automated_software_developer.agent.portfolio.registry import PortfolioRegistry
from automated_software_developer.agent.portfolio.schemas import DeployRecord, RegistryEntry
from automated_software_developer.agent.security import redact_sensitive_text


class DashboardRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for read-only portfolio dashboard endpoints."""

    registry: PortfolioRegistry

    def do_GET(self) -> None:  # noqa: N802
        """Handle read-only GET endpoints."""
        status_code, payload = resolve_dashboard_request(self.registry, self.path)
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        """Silence default server request logging by default."""
        del format, args


def resolve_dashboard_request(registry: PortfolioRegistry, path: str) -> tuple[int, dict[str, Any]]:
    """Resolve a dashboard request path into status code and JSON payload."""
    parsed = urlparse(path)
    if parsed.path == "/health":
        return 200, {"status": "ok"}
    if parsed.path == "/projects":
        projects = [
            serialize_entry(entry)
            for entry in registry.list_entries(include_archived=True)
        ]
        return 200, {"projects": projects, "count": len(projects)}
    if parsed.path.startswith("/projects/"):
        project_id = unquote(parsed.path.split("/projects/", maxsplit=1)[1]).strip()
        if not project_id:
            return 400, {"error": "project id is required"}
        entry = registry.get(project_id)
        if entry is None:
            return 404, {"error": f"project '{project_id}' not found"}
        return 200, {"project": serialize_entry(entry)}
    return 404, {"error": "not found"}


def serve_dashboard(
    registry: PortfolioRegistry,
    *,
    host: str,
    port: int,
) -> None:
    """Run dashboard HTTP server until interrupted."""

    class _Handler(DashboardRequestHandler):
        pass

    _Handler.registry = registry

    server = ThreadingHTTPServer((host, port), _Handler)
    server.serve_forever()


def serialize_entry(entry: RegistryEntry) -> dict[str, Any]:
    """Serialize registry entry with secret-safe redaction."""
    payload = entry.to_dict()
    if isinstance(payload.get("last_deploy"), dict):
        payload["last_deploy"] = _serialize_deploy(payload["last_deploy"])
    redacted = _redact(payload)
    if not isinstance(redacted, dict):
        raise TypeError("Serialized registry entry must be a JSON object.")
    return redacted


def _serialize_deploy(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize deploy payload before response."""
    record = DeployRecord.from_dict(payload)
    return asdict(record)


def _redact(value: Any) -> Any:
    """Recursively redact secret-like values from payload."""
    if isinstance(value, str):
        return redact_sensitive_text(value)
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for key, item in value.items():
            output[str(key)] = _redact(item)
        return output
    return value
