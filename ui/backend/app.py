"""FastAPI application for the Autonomous Engineering Console."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from automated_software_developer.agent.plugins.registry import PluginRegistry
from ui.backend.events import Event, EventBroker
from ui.backend.models import (
    ArtifactResponse,
    EventPayload,
    LaunchResponse,
    PlanResponse,
    PluginResponse,
    ProgressResponse,
    ProjectCreateRequest,
    ProjectResponse,
    ProjectUpdateRequirements,
    RequirementsMessageRequest,
    RequirementsRefineRequest,
    RequirementsRefineResponse,
    RequirementsResponse,
    RequirementsSessionRequest,
    RequirementsValidateRequest,
    RequirementsValidateResponse,
    RunResponse,
)
from ui.backend.services import LaunchCoordinator, PlanBuilder, RequirementsService
from ui.backend.session_store import AECSessionStore
from ui.backend.store import ProjectStore


class BackendState:
    """Holds shared state for the API."""

    def __init__(self) -> None:
        self.store = ProjectStore()
        self.broker = EventBroker()
        self.requirements = RequirementsService()
        self.plan_builder = PlanBuilder()
        self.launcher = LaunchCoordinator(store=self.store, broker=self.broker)
        self.sessions = AECSessionStore()
        self.plugins = PluginRegistry()


def create_app() -> FastAPI:
    """Create the FastAPI application."""
    app = FastAPI(title="Autonomous Engineering Console API")
    state = BackendState()

    @app.get("/api/projects", response_model=list[ProjectResponse])
    def list_projects() -> list[ProjectResponse]:
        return state.store.list_projects()

    @app.post("/api/projects", response_model=ProjectResponse)
    def create_project(payload: ProjectCreateRequest) -> ProjectResponse:
        return state.store.create_project(name=payload.name, idea=payload.idea)

    @app.get("/api/projects/{project_id}", response_model=ProjectResponse)
    def get_project(project_id: str) -> ProjectResponse:
        try:
            return state.store.get_project(project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc

    @app.put("/api/projects/{project_id}/requirements", response_model=ProjectResponse)
    def update_requirements(project_id: str, payload: ProjectUpdateRequirements) -> ProjectResponse:
        try:
            return state.store.update_requirements(project_id, payload.requirements)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/plan", response_model=PlanResponse)
    def get_plan(project_id: str) -> PlanResponse:
        try:
            project = state.store.get_project(project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc
        if not project.requirements:
            raise HTTPException(status_code=400, detail="Project requirements missing")
        plan = state.plan_builder.build(project.requirements)
        state.store.update_plan(project_id, plan.model_dump())
        return plan

    @app.post("/api/projects/{project_id}/launch", response_model=LaunchResponse)
    def launch_project(project_id: str) -> LaunchResponse:
        try:
            launch_id, status = state.launcher.launch(project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        progress = state.store.get_progress(project_id)
        if progress:
            state.sessions.save_progress_snapshot(project_id, progress)
        return LaunchResponse(
            launch_id=launch_id,
            status=status,
            message="Autonomous build started.",
        )

    @app.post("/api/projects/{project_id}/pause", response_model=ProjectResponse)
    def pause_project(project_id: str) -> ProjectResponse:
        try:
            state.launcher.pause(project_id)
            return state.store.get_project(project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc

    @app.post("/api/projects/{project_id}/resume", response_model=ProjectResponse)
    def resume_project(project_id: str) -> ProjectResponse:
        try:
            state.launcher.resume(project_id)
            return state.store.get_project(project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc

    @app.post("/api/projects/{project_id}/cancel", response_model=ProjectResponse)
    def cancel_project(project_id: str) -> ProjectResponse:
        try:
            state.launcher.cancel(project_id)
            return state.store.get_project(project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc

    @app.post("/api/requirements/sessions", response_model=RequirementsResponse)
    def start_requirements_session(
        payload: RequirementsSessionRequest,
    ) -> RequirementsResponse:
        response = state.requirements.start(payload.idea)
        state.sessions.create_session(payload.idea, session_id=response.session_id)
        state.sessions.add_message(response.session_id, "user", payload.idea)
        return RequirementsResponse(
            session_id=response.session_id,
            questions=response.questions,
            suggestions=response.suggestions,
            draft=response.draft,
        )

    @app.post(
        "/api/requirements/sessions/{session_id}/messages",
        response_model=RequirementsResponse,
    )
    def add_requirements_message(
        session_id: str, payload: RequirementsMessageRequest
    ) -> RequirementsResponse:
        try:
            response = state.requirements.message(session_id, payload.message)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        state.sessions.add_message(session_id, "user", payload.message)
        return RequirementsResponse(
            session_id=response.session_id,
            questions=response.questions,
            suggestions=response.suggestions,
            draft=response.draft,
        )

    @app.post(
        "/api/requirements/sessions/{session_id}/finalize",
        response_model=dict,
    )
    def finalize_requirements(session_id: str) -> dict:
        try:
            draft = state.requirements.finalize(session_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "summary": draft.summary,
            "goals": list(draft.goals),
            "constraints": list(draft.constraints),
            "functional_requirements": list(draft.functional_requirements),
            "non_functional_requirements": list(draft.non_functional_requirements),
            "acceptance_criteria": list(draft.acceptance_criteria),
            "risks": list(draft.risks),
            "compliance_flags": list(draft.compliance_flags),
        }

    @app.post("/api/requirements/refine", response_model=RequirementsRefineResponse)
    def refine_requirements(payload: RequirementsRefineRequest) -> RequirementsRefineResponse:
        refinement = state.requirements.refine(payload.markdown)
        return RequirementsRefineResponse(
            markdown=refinement.markdown,
            summary=refinement.summary,
        )

    @app.post("/api/requirements/validate", response_model=RequirementsValidateResponse)
    def validate_requirements(
        payload: RequirementsValidateRequest,
    ) -> RequirementsValidateResponse:
        validation = state.requirements.validate(payload.markdown)
        return RequirementsValidateResponse(
            missing_sections=validation.missing_sections,
            warnings=validation.warnings,
        )

    @app.post("/api/sessions", response_model=RequirementsResponse)
    def start_session_alias(payload: RequirementsSessionRequest) -> RequirementsResponse:
        return start_requirements_session(payload)

    @app.post("/api/sessions/{session_id}/messages", response_model=RequirementsResponse)
    def add_session_message_alias(
        session_id: str, payload: RequirementsMessageRequest
    ) -> RequirementsResponse:
        return add_requirements_message(session_id, payload)

    @app.get("/api/projects/{project_id}/progress", response_model=ProgressResponse)
    def get_progress(project_id: str) -> ProgressResponse:
        try:
            progress = state.store.get_progress(project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc
        if not progress:
            raise HTTPException(status_code=404, detail="Progress not found")
        return ProgressResponse(**progress)

    @app.get("/api/projects/{project_id}/artifacts", response_model=list[ArtifactResponse])
    def get_artifacts(project_id: str) -> list[ArtifactResponse]:
        try:
            artifacts = state.store.list_artifacts(project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc
        return [ArtifactResponse(**artifact) for artifact in artifacts]

    @app.get("/api/projects/{project_id}/runs", response_model=list[RunResponse])
    def get_runs(project_id: str) -> list[RunResponse]:
        try:
            runs = state.store.list_runs(project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc
        return [RunResponse(**run) for run in runs]

    @app.get("/api/projects/{project_id}/incidents")
    def get_incidents(project_id: str) -> dict:
        _ = project_id
        return {"incidents": []}

    @app.get("/api/projects/{project_id}/deployments")
    def get_deployments(project_id: str) -> dict:
        _ = project_id
        return {"deployments": []}

    @app.get("/api/projects/{project_id}/metrics")
    def get_metrics(project_id: str) -> dict:
        _ = project_id
        return {"metrics": []}

    @app.get("/api/plugins", response_model=list[PluginResponse])
    def list_plugins() -> list[PluginResponse]:
        plugins = state.plugins.list_plugins()
        return [
            PluginResponse(
                plugin_id=plugin.plugin_id,
                name=plugin.name,
                enabled=plugin.enabled,
            )
            for plugin in plugins
        ]

    @app.post("/api/plugins/{plugin_id}/enable", response_model=PluginResponse)
    def enable_plugin(plugin_id: str) -> PluginResponse:
        try:
            plugin = state.plugins.enable_plugin(plugin_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return PluginResponse(
            plugin_id=plugin.plugin_id,
            name=plugin.name,
            enabled=plugin.enabled,
        )

    @app.post("/api/plugins/{plugin_id}/disable", response_model=PluginResponse)
    def disable_plugin(plugin_id: str) -> PluginResponse:
        try:
            plugin = state.plugins.disable_plugin(plugin_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return PluginResponse(
            plugin_id=plugin.plugin_id,
            name=plugin.name,
            enabled=plugin.enabled,
        )

    @app.get("/api/events/{project_id}/sse")
    async def stream_events(project_id: str) -> StreamingResponse:
        async def event_generator() -> AsyncGenerator[str, None]:
            for event in state.broker.history(project_id):
                yield _format_sse(event)
            queue = state.broker.subscribe(project_id)
            try:
                while True:
                    event = await queue.get()
                    yield _format_sse(event)
            finally:
                state.broker.unsubscribe(project_id, queue)

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    @app.websocket("/api/events/{project_id}/ws")
    async def websocket_events(websocket: WebSocket, project_id: str) -> None:
        await websocket.accept()
        for event in state.broker.history(project_id):
            await websocket.send_json(_event_payload(event))
        queue = state.broker.subscribe(project_id)
        try:
            while True:
                event = await queue.get()
                await websocket.send_json(_event_payload(event))
        except WebSocketDisconnect:
            state.broker.unsubscribe(project_id, queue)

    return app


def _format_sse(event: Event) -> str:
    payload = json.dumps(_event_payload(event))
    return f"data: {payload}\n\n"


def _event_payload(event: Event) -> dict:
    payload = EventPayload(
        event_id=event.event_id,
        project_id=event.project_id,
        event_type=event.event_type,
        message=event.message,
        timestamp=event.timestamp,
        reason=event.reason,
        artifact_url=event.artifact_url,
    )
    return payload.model_dump(mode="json")


app = create_app()
