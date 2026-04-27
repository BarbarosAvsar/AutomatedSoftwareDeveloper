"""Local no-dependency web UI for managing AutoSD runs and operations."""

from __future__ import annotations

# ruff: noqa: E501
import json
import logging
import subprocess  # nosec B404
import sys
import threading
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from automated_software_developer.agent.config_validation import (
    require_positive_int,
    validate_execution_mode,
)
from automated_software_developer.agent.orchestrator import AgentConfig, SoftwareDevelopmentAgent
from automated_software_developer.agent.providers.base import LLMProvider
from automated_software_developer.agent.security import redact_sensitive_text

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunRequest:
    """Validated request payload for starting an AutoSD run."""

    requirements_text: str | None
    requirements_file: Path | None
    output_dir: Path
    execution_mode: str
    provider: str
    model: str
    max_task_attempts: int
    timeout_seconds: int
    max_stories_per_sprint: int
    parallel_prompt_workers: int


@dataclass
class RunRecord:
    """Runtime and summary metadata for a UI-initiated run."""

    run_id: str
    created_at: str
    output_dir: str
    execution_mode: str
    provider: str
    status: str = "queued"
    stage: str = "Queued"
    progress_percent: float = 0.0
    tasks_completed: int = 0
    tasks_total: int = 0
    error_message: str | None = None
    actionable_error: str | None = None
    summary: dict[str, Any] | None = None


@dataclass
class OperationRecord:
    """Result metadata for operation-center commands."""

    operation_id: str
    command: list[str]
    created_at: str
    status: str
    exit_code: int
    output_snippet: str


@dataclass
class ControlCenterState:
    """Thread-safe mutable state backing the control center UI."""

    provider_factory: Callable[[str, str, Path | None], LLMProvider]
    runs: dict[str, RunRecord] = field(default_factory=dict)
    operations: list[OperationRecord] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def create_run(self, request: RunRequest) -> RunRecord:
        """Create and store a new run record."""
        record = RunRecord(
            run_id=uuid.uuid4().hex,
            created_at=datetime.now(tz=UTC).isoformat(),
            output_dir=str(request.output_dir),
            execution_mode=request.execution_mode,
            provider=request.provider,
        )
        with self.lock:
            self.runs[record.run_id] = record
        return record

    def update_run(self, run_id: str, **updates: Any) -> None:
        """Apply partial updates for a run if present."""
        with self.lock:
            run = self.runs.get(run_id)
            if run is None:
                return
            for key, value in updates.items():
                setattr(run, key, value)

    def add_operation(self, record: OperationRecord) -> None:
        """Append a completed operation record."""
        with self.lock:
            self.operations.insert(0, record)
            del self.operations[25:]


def _parse_run_request(payload: dict[str, Any]) -> RunRequest:
    """Validate and normalize run request payload."""
    requirements_text = payload.get("requirements_text")
    requirements_file_raw = payload.get("requirements_file")
    if bool(requirements_text) == bool(requirements_file_raw):
        raise ValueError("Provide either requirements_text or requirements_file.")
    requirements_file = Path(str(requirements_file_raw)) if requirements_file_raw else None
    if requirements_file is not None and not requirements_file.exists():
        raise ValueError(f"requirements_file does not exist: {requirements_file}")
    if requirements_text is not None and not str(requirements_text).strip():
        raise ValueError("requirements_text must be non-empty.")

    output_dir = Path(str(payload.get("output_dir", "generated_project")))
    execution_mode = validate_execution_mode(str(payload.get("execution_mode", "direct")))
    provider = str(payload.get("provider", "openai"))
    model = str(payload.get("model", "gpt-5.3-codex"))
    max_task_attempts = require_positive_int(int(payload.get("max_task_attempts", 4)), "max_task")
    timeout_seconds = require_positive_int(int(payload.get("timeout_seconds", 240)), "timeout")
    max_stories_per_sprint = require_positive_int(
        int(payload.get("max_stories_per_sprint", 2)),
        "max_stories_per_sprint",
    )
    parallel_prompt_workers = require_positive_int(
        int(payload.get("parallel_prompt_workers", 1)),
        "parallel_prompt_workers",
    )
    return RunRequest(
        requirements_text=str(requirements_text) if requirements_text is not None else None,
        requirements_file=requirements_file,
        output_dir=output_dir,
        execution_mode=execution_mode,
        provider=provider,
        model=model,
        max_task_attempts=max_task_attempts,
        timeout_seconds=timeout_seconds,
        max_stories_per_sprint=max_stories_per_sprint,
        parallel_prompt_workers=parallel_prompt_workers,
    )


def _actionable_error(message: str) -> str:
    """Map common failures to actionable guidance text."""
    text = message.lower()
    if "openai_api_key" in text:
        return "Set OPENAI_API_KEY or switch provider to mock for local testing."
    if "requirements" in text and "non-empty" in text:
        return "Provide requirements text or a valid requirements file path."
    if "no such file" in text:
        return "Verify file paths and output directory permissions."
    return "See autosd.log for details and retry with adjusted inputs."


def _summarize_run(summary: Any) -> dict[str, Any]:
    """Serialize RunSummary dataclass into JSON-safe payload."""
    artifact_paths = {
        "refined_requirements": str(summary.refined_spec_path) if summary.refined_spec_path else None,
        "backlog": str(summary.backlog_path) if summary.backlog_path else None,
        "design_doc": str(summary.design_doc_path) if summary.design_doc_path else None,
        "progress": str(Path(summary.output_dir) / ".autosd" / "progress.json"),
        "sprint_log": str(summary.sprint_log_path) if summary.sprint_log_path else None,
        "prompt_journal": str(summary.journal_path) if summary.journal_path else None,
        "platform_plan": str(summary.platform_plan_path) if summary.platform_plan_path else None,
        "capability_graph": str(summary.capability_graph_path) if summary.capability_graph_path else None,
    }
    return {
        "output_dir": str(summary.output_dir),
        "project_name": summary.project_name,
        "tasks": {"completed": summary.tasks_completed, "total": summary.tasks_total},
        "readiness_level": summary.readiness_level,
        "blocking_reasons": summary.blocking_reasons,
        "execution_mode": {
            "requested": summary.requested_execution_mode,
            "selected": summary.selected_execution_mode,
            "reason": summary.execution_mode_reason,
        },
        "artifacts": artifact_paths,
        "verification_results": [
            {
                "command": result.command,
                "exit_code": result.exit_code,
                "duration_seconds": result.duration_seconds,
            }
            for result in summary.verification_results
        ],
    }


def _tail_log(path: Path, *, lines: int = 40) -> str:
    """Read and redact the most recent log lines from a local file."""
    if lines <= 0:
        raise ValueError("lines must be positive.")
    if not path.exists():
        return ""
    content = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    snippet = "\n".join(content[-lines:])
    return redact_sensitive_text(snippet)


def _load_progress(output_dir: Path) -> tuple[str, float]:
    """Load current stage and percent from .autosd/progress.json when available."""
    progress_path = output_dir / ".autosd" / "progress.json"
    if not progress_path.exists():
        return "Queued", 0.0
    try:
        payload = json.loads(progress_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "Running", 0.0
    phase = str(payload.get("phase", "Running"))
    percent = float(payload.get("percent_complete", 0.0))
    return phase, round(percent, 2)


def _run_agent(state: ControlCenterState, run_id: str, request: RunRequest, log_file: Path) -> None:
    """Execute a run in a background thread and update state."""
    state.update_run(run_id, status="running", stage="Starting")
    try:
        provider: LLMProvider = state.provider_factory(
            request.provider,
            request.model,
            None,
        )
        requirements = (
            request.requirements_file.read_text(encoding="utf-8")
            if request.requirements_file is not None
            else request.requirements_text
        )
        if requirements is None:
            raise ValueError("requirements were empty after parsing request.")
        config = AgentConfig(
            max_task_attempts=request.max_task_attempts,
            command_timeout_seconds=request.timeout_seconds,
            max_stories_per_sprint=request.max_stories_per_sprint,
            execution_mode=request.execution_mode,
            parallel_prompt_workers=request.parallel_prompt_workers,
        )
        agent = SoftwareDevelopmentAgent(provider=provider, config=config)
        summary = agent.run(requirements=requirements, output_dir=request.output_dir)
        phase, percent = _load_progress(request.output_dir)
        state.update_run(
            run_id,
            status="completed",
            stage=phase,
            progress_percent=percent,
            tasks_completed=summary.tasks_completed,
            tasks_total=summary.tasks_total,
            summary=_summarize_run(summary),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Control Center run %s failed", run_id)
        phase, percent = _load_progress(request.output_dir)
        message = redact_sensitive_text(str(exc))
        state.update_run(
            run_id,
            status="failed",
            stage=phase if phase else "Failed",
            progress_percent=percent,
            error_message=message,
            actionable_error=_actionable_error(message),
        )
    finally:
        with state.lock:
            run = state.runs.get(run_id)
        if run is not None and not run.stage:
            state.update_run(run_id, stage="Finished")
        log_file.touch(exist_ok=True)


def _run_operation(command: list[str]) -> OperationRecord:
    """Execute a local autosd operation command and capture redacted snippet."""
    completed = subprocess.run(command, check=False, capture_output=True, text=True)  # nosec B603
    combined = f"{completed.stdout}\n{completed.stderr}".strip()
    snippet = redact_sensitive_text("\n".join(combined.splitlines()[-20:]))
    return OperationRecord(
        operation_id=uuid.uuid4().hex,
        command=command,
        created_at=datetime.now(tz=UTC).isoformat(),
        status="passed" if completed.returncode == 0 else "failed",
        exit_code=completed.returncode,
        output_snippet=snippet,
    )


def _run_local_operation(operation_name: str) -> OperationRecord:
    """Run a supported operation command."""
    if operation_name == "doctor":
        return _run_operation([sys.executable, "-m", "automated_software_developer", "doctor"])
    if operation_name == "verify-factory":
        return _run_operation(
            [sys.executable, "-m", "automated_software_developer", "verify-factory"]
        )
    raise ValueError("Unsupported operation. Use doctor or verify-factory.")


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    """Write JSON response payload."""
    body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _parse_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    """Decode request body JSON payload."""
    raw_size = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(raw_size).decode("utf-8") if raw_size else "{}"
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("JSON payload must be an object.")
    return payload


def _artifact_links(run: RunRecord) -> list[dict[str, str]]:
    """Build clickable artifact links from run summary."""
    if run.summary is None:
        return []
    artifacts = run.summary.get("artifacts", {})
    output: list[dict[str, str]] = []
    if not isinstance(artifacts, dict):
        return output
    for name, path in artifacts.items():
        if isinstance(path, str) and path:
            resolved = Path(path).resolve()
            output.append({"name": name, "path": str(resolved), "url": resolved.as_uri()})
    return output


def resolve_control_center_request(
    *,
    state: ControlCenterState,
    method: str,
    raw_path: str,
    body: dict[str, Any] | None,
    log_file: Path,
) -> tuple[int, dict[str, Any]]:
    """Resolve API and static routes for control center."""
    parsed = urlparse(raw_path)
    if parsed.path == "/":
        return HTTPStatus.OK, {"html": CONTROL_CENTER_HTML}
    if parsed.path == "/api/onboarding" and method == "GET":
        return HTTPStatus.OK, {
            "title": "Welcome to AutoSD Control Center",
            "steps": [
                "Start a run from the wizard with requirements text or a file path.",
                "Monitor stage badges, progress, and redacted logs in real time.",
                "Review generated artifacts and run operations checks.",
            ],
            "log_file": str(log_file.resolve()),
            "telemetry_default": "off",
        }
    if parsed.path == "/api/runs" and method == "POST":
        request = _parse_run_request(body or {})
        record = state.create_run(request)
        thread = threading.Thread(
            target=_run_agent,
            kwargs={"state": state, "run_id": record.run_id, "request": request, "log_file": log_file},
            daemon=True,
        )
        thread.start()
        return HTTPStatus.ACCEPTED, {"run": asdict(record)}
    if parsed.path == "/api/runs" and method == "GET":
        query = parse_qs(parsed.query)
        status_filter = query.get("status", [""])[0].strip()
        search = query.get("search", [""])[0].strip().lower()
        with state.lock:
            rows = list(state.runs.values())
        rows.sort(key=lambda item: item.created_at, reverse=True)
        filtered: list[RunRecord] = []
        for row in rows:
            if status_filter and row.status != status_filter:
                continue
            searchable = f"{row.output_dir} {row.execution_mode} {row.provider}".lower()
            if search and search not in searchable:
                continue
            phase, percent = _load_progress(Path(row.output_dir))
            row.stage = phase if row.status == "running" else row.stage
            row.progress_percent = percent if row.status == "running" else row.progress_percent
            filtered.append(row)
        return HTTPStatus.OK, {"runs": [asdict(item) for item in filtered]}
    if parsed.path.startswith("/api/runs/") and method == "GET":
        run_id = parsed.path.split("/api/runs/", maxsplit=1)[1]
        with state.lock:
            run_record = state.runs.get(run_id)
        if run_record is None:
            return HTTPStatus.NOT_FOUND, {"error": "run not found"}
        if run_record.status == "running":
            phase, percent = _load_progress(Path(run_record.output_dir))
            state.update_run(run_id, stage=phase, progress_percent=percent)
            with state.lock:
                run_record = state.runs[run_id]
        payload = asdict(run_record)
        payload["artifacts"] = _artifact_links(run_record)
        return HTTPStatus.OK, {"run": payload, "logs": _tail_log(log_file)}
    if parsed.path == "/api/operations" and method == "POST":
        operation_name = str((body or {}).get("operation", "")).strip()
        operation_record = _run_local_operation(operation_name)
        state.add_operation(operation_record)
        return HTTPStatus.OK, {"operation": asdict(operation_record)}
    if parsed.path == "/api/operations" and method == "GET":
        with state.lock:
            operations = [asdict(item) for item in state.operations]
        return HTTPStatus.OK, {"operations": operations}
    return HTTPStatus.NOT_FOUND, {"error": "not found"}


class ControlCenterRequestHandler(BaseHTTPRequestHandler):
    """HTTP handler for AutoSD control center UI and API endpoints."""

    state: ControlCenterState
    log_file: Path

    def do_GET(self) -> None:  # noqa: N802
        """Handle GET requests."""
        status, payload = resolve_control_center_request(
            state=self.state,
            method="GET",
            raw_path=self.path,
            body=None,
            log_file=self.log_file,
        )
        if self.path == "/":
            html = payload["html"].encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
            return
        _json_response(self, status, payload)

    def do_POST(self) -> None:  # noqa: N802
        """Handle POST requests."""
        try:
            body = _parse_body(self)
            status, payload = resolve_control_center_request(
                state=self.state,
                method="POST",
                raw_path=self.path,
                body=body,
                log_file=self.log_file,
            )
            _json_response(self, status, payload)
        except ValueError as exc:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": redact_sensitive_text(str(exc))})

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        """Silence base request logs to keep output clean."""
        del format, args


def serve_control_center(
    *,
    host: str,
    port: int,
    provider_factory: Callable[[str, str, Path | None], LLMProvider],
    log_file: Path,
) -> None:
    """Start the local AutoSD Control Center HTTP server."""

    class _Handler(ControlCenterRequestHandler):
        pass

    _Handler.state = ControlCenterState(provider_factory=provider_factory)
    _Handler.log_file = log_file
    server = ThreadingHTTPServer((host, port), _Handler)
    server.serve_forever()


CONTROL_CENTER_HTML = """<!doctype html>
<html lang=\"en\">
<head>
<meta charset=\"utf-8\" />
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
<title>AutoSD Control Center</title>
<style>
:root { color-scheme: light dark; }
body { font-family: system-ui, sans-serif; margin: 0; background: #0b1020; color: #e8ecf5; }
header { padding: 1rem 1.25rem; background: #111935; position: sticky; top: 0; }
main { display: grid; grid-template-columns: 220px 1fr; min-height: calc(100vh - 70px); }
nav { border-right: 1px solid #2a3353; padding: 1rem; }
nav button { display:block; width:100%; margin:.3rem 0; padding:.55rem; text-align:left; border:1px solid #42507d; background:#131d3a; color:#e8ecf5; border-radius:8px; }
section { display:none; padding: 1rem 1.25rem; }
section.active { display:block; }
.card { border:1px solid #2a3353; border-radius:10px; padding:1rem; margin-bottom:1rem; background:#10182f; }
label { display:block; margin:.5rem 0 .2rem; font-weight:600; }
input, textarea, select { width:100%; padding:.55rem; border-radius:8px; border:1px solid #42507d; background:#0b1020; color:#fff; }
textarea { min-height: 120px; }
button.primary { background:#2f6feb; border:none; padding:.6rem .9rem; border-radius:8px; color:white; font-weight:700; }
.badge { padding:.15rem .5rem; border-radius:999px; font-size:.8rem; border:1px solid #5c6b93; }
.grid2 { display:grid; grid-template-columns: repeat(auto-fit,minmax(220px,1fr)); gap: .75rem; }
pre { white-space: pre-wrap; max-height: 240px; overflow:auto; background:#0a0f1f; padding:.8rem; border-radius:8px; border:1px solid #2a3353; }
small.muted { color:#9faccd; }
</style>
</head>
<body>
<header><strong>AutoSD Control Center</strong> <small class="muted">Telemetry default: OFF</small></header>
<main>
<nav aria-label="Sections">
<button data-tab="onboarding">Onboarding</button>
<button data-tab="wizard">New Run</button>
<button data-tab="monitor">Run Monitor</button>
<button data-tab="results">Results</button>
<button data-tab="operations">Operations</button>
<button data-tab="history">History</button>
</nav>
<div>
<section id="onboarding" class="active"><div class="card" id="onboarding-card"></div></section>
<section id="wizard">
<div class="card">
<h2>New Run Wizard</h2>
<label for="requirements_text">Requirements text</label><textarea id="requirements_text" placeholder="Paste requirements text"></textarea>
<label for="requirements_file">or Requirements file path</label><input id="requirements_file" placeholder="/path/to/requirements.md" />
<div class="grid2">
<div><label for="output_dir">Output directory</label><input id="output_dir" value="generated_project" /></div>
<div><label for="execution_mode">Execution mode</label><select id="execution_mode"><option>direct</option><option>planning</option><option>auto</option></select></div>
</div>
<details><summary>Advanced options</summary>
<div class="grid2">
<div><label for="provider">Provider</label><select id="provider"><option>openai</option><option>resilient</option><option>mock</option></select></div>
<div><label for="model">Model</label><input id="model" value="gpt-5.3-codex" /></div>
<div><label for="max_task_attempts">Max task attempts</label><input id="max_task_attempts" value="4" /></div>
<div><label for="timeout_seconds">Timeout seconds</label><input id="timeout_seconds" value="240" /></div>
</div>
</details>
<p><button class="primary" id="start-run">Start Run</button> <span id="wizard-message" role="status" aria-live="polite"></span></p>
</div></section>
<section id="monitor"><div class="card"><h2>Run Monitor</h2><div id="monitor-body">No run selected yet.</div></div></section>
<section id="results"><div class="card"><h2>Results</h2><div id="results-body">Run a project to view summary and artifacts.</div></div></section>
<section id="operations"><div class="card"><h2>Operations</h2>
<p><button class="primary" data-op="doctor">Run autosd doctor</button> <button class="primary" data-op="verify-factory">Run autosd verify-factory</button></p>
<div id="operations-body"></div></div></section>
<section id="history"><div class="card"><h2>Recent Runs</h2>
<label for="history-filter">Status filter</label><select id="history-filter"><option value="">all</option><option>queued</option><option>running</option><option>completed</option><option>failed</option></select>
<label for="history-search">Search</label><input id="history-search" placeholder="output dir or mode"/>
<div id="history-body"></div></div></section>
</div>
</main>
<script>
let currentRunId = null;
function tab(id){document.querySelectorAll('section').forEach(s=>s.classList.toggle('active', s.id===id));}
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>tab(b.dataset.tab));

async function api(path, options={}){const r=await fetch(path,{headers:{'Content-Type':'application/json'},...options});return r.json();}
function esc(v){return String(v??'').replace(/[&<>]/g,s=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[s]));}

async function loadOnboarding(){const d=await api('/api/onboarding');document.getElementById('onboarding-card').innerHTML=`<h2>${esc(d.title)}</h2><ol>${d.steps.map(s=>`<li>${esc(s)}</li>`).join('')}</ol><p><strong>Debug log:</strong> ${esc(d.log_file)}</p>`;}

async function startRun(){
 const payload={requirements_text:requirements_text.value,requirements_file:requirements_file.value,output_dir:output_dir.value,execution_mode:execution_mode.value,provider:provider.value,model:model.value,max_task_attempts:Number(max_task_attempts.value),timeout_seconds:Number(timeout_seconds.value)};
 if(payload.requirements_text.trim() && payload.requirements_file.trim()){wizard-message.textContent='Provide text OR file path, not both.'; return;}
 if(!payload.requirements_text.trim() && !payload.requirements_file.trim()){wizard-message.textContent='Provide requirements text or file path.'; return;}
 const res=await api('/api/runs',{method:'POST',body:JSON.stringify(payload)});
 if(res.error){wizard-message.textContent=res.error;return;}
 currentRunId=res.run.run_id; wizard-message.textContent=`Run started: ${currentRunId}`; tab('monitor');
}
start-run.onclick=startRun;

async function refreshCurrent(){
 if(!currentRunId){return;}
 const data=await api(`/api/runs/${currentRunId}`); if(data.error){return;}
 const r=data.run;
 monitor-body.innerHTML=`<p><span class='badge'>${esc(r.status)}</span> <span class='badge'>${esc(r.stage)}</span> Progress: <strong>${esc(r.progress_percent)}%</strong></p>
 <p>Output: <code>${esc(r.output_dir)}</code></p>
 ${r.error_message?`<p><strong>Error:</strong> ${esc(r.error_message)}<br/><strong>Action:</strong> ${esc(r.actionable_error||'')}</p>`:''}
 <h3>Recent logs</h3><pre>${esc(data.logs||'')}</pre>`;
 if(r.summary){
   results-body.innerHTML=`<p><strong>Project:</strong> ${esc(r.summary.project_name)}<br/><strong>Tasks:</strong> ${esc(r.summary.tasks.completed)}/${esc(r.summary.tasks.total)}</p>
   <p><strong>Readiness:</strong> ${esc(r.summary.readiness_level)}</p>
   <h3>Artifacts</h3><ul>${(data.run.artifacts||[]).map(a=>`<li><a href='${esc(a.url)}'>${esc(a.name)}</a> <small>${esc(a.path)}</small></li>`).join('')}</ul>`;
 }
}

async function refreshHistory(){
 const q=new URLSearchParams({status:history-filter.value,search:history-search.value});
 const data=await api('/api/runs?'+q.toString());
 history-body.innerHTML=(data.runs||[]).map(r=>`<div class='card'><p><button onclick="currentRunId='${esc(r.run_id)}';tab('monitor')">Open</button> <strong>${esc(r.run_id.slice(0,8))}</strong> <span class='badge'>${esc(r.status)}</span> <span class='badge'>${esc(r.stage)}</span></p><p>${esc(r.output_dir)} · ${esc(r.execution_mode)}</p></div>`).join('')||'<p>No runs yet.</p>';
}
history-filter.onchange=refreshHistory; history-search.oninput=refreshHistory;

async function refreshOperations(){const d=await api('/api/operations');operations-body.innerHTML=(d.operations||[]).map(o=>`<div class='card'><p><span class='badge'>${esc(o.status)}</span> ${esc(o.command.join(' '))}</p><pre>${esc(o.output_snippet)}</pre></div>`).join('')||'<p>No operations yet.</p>'}

document.querySelectorAll('[data-op]').forEach(btn=>btn.onclick=async()=>{await api('/api/operations',{method:'POST',body:JSON.stringify({operation:btn.dataset.op})}); await refreshOperations();});

setInterval(()=>{refreshCurrent();refreshHistory();}, 2000);
setInterval(refreshOperations, 4000);
loadOnboarding(); refreshHistory(); refreshOperations();
</script>
</body>
</html>
"""
