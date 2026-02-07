"""FastAPI application for the Autonomous Engineering Console."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from ui.backend.events import Event, EventBroker
from ui.backend.models import (
    EventPayload,
    LaunchResponse,
    PlanResponse,
    ProjectCreateRequest,
    ProjectResponse,
    ProjectUpdateRequirements,
    RequirementsMessageRequest,
    RequirementsResponse,
    RequirementsSessionRequest,
)
from ui.backend.services import LaunchCoordinator, PlanBuilder, RequirementsService
from ui.backend.store import ProjectStore


class BackendState:
    """Holds shared state for the API."""

    def __init__(self) -> None:
        self.store = ProjectStore()
        self.broker = EventBroker()
        self.requirements = RequirementsService()
        self.plan_builder = PlanBuilder()
        self.launcher = LaunchCoordinator(store=self.store, broker=self.broker)


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
    def update_requirements(
        project_id: str, payload: ProjectUpdateRequirements
    ) -> ProjectResponse:
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
        return LaunchResponse(
            launch_id=launch_id,
            status=status,
            message="Autonomous build started.",
        )

    @app.post("/api/requirements/sessions", response_model=RequirementsResponse)
    def start_requirements_session(
        payload: RequirementsSessionRequest,
    ) -> RequirementsResponse:
        response = state.requirements.start(payload.idea)
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
