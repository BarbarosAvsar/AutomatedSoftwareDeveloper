from fastapi.testclient import TestClient

from ui.backend.app import create_app


def test_project_creation_and_plan_flow() -> None:
    app = create_app()
    client = TestClient(app)

    create_response = client.post("/api/projects", json={"name": "Nova", "idea": "AI console"})
    assert create_response.status_code == 200
    project = create_response.json()
    project_id = project["id"]

    session_response = client.post(
        "/api/requirements/sessions", json={"idea": "AI console"}
    )
    assert session_response.status_code == 200
    session_id = session_response.json()["session_id"]

    message_response = client.post(
        f"/api/requirements/sessions/{session_id}/messages",
        json={"message": "Needs real-time dashboards"},
    )
    assert message_response.status_code == 200
    draft = message_response.json()["draft"]
    assert "real-time" in " ".join(draft["functional_requirements"]).lower()

    requirements_text = "\n".join(draft["functional_requirements"])
    requirements_response = client.put(
        f"/api/projects/{project_id}/requirements",
        json={"requirements": requirements_text},
    )
    assert requirements_response.status_code == 200

    plan_response = client.get(f"/api/projects/{project_id}/plan")
    assert plan_response.status_code == 200
    plan = plan_response.json()
    assert "architecture" in plan


def test_requirements_refine_and_validate() -> None:
    app = create_app()
    client = TestClient(app)

    refine_response = client.post(
        "/api/requirements/refine",
        json={"markdown": "Build an AEC with chat and progress."},
    )
    assert refine_response.status_code == 200
    assert "Requirements" in refine_response.json()["markdown"]

    validate_response = client.post(
        "/api/requirements/validate",
        json={"markdown": "# Requirements\n## Functional requirements\n- Chat\n"},
    )
    assert validate_response.status_code == 200
    assert "Problem / Goals" in validate_response.json()["missing_sections"]


def test_launch_progress_endpoint() -> None:
    app = create_app()
    client = TestClient(app)

    create_response = client.post("/api/projects", json={"name": "Nova"})
    project_id = create_response.json()["id"]
    client.put(
        f"/api/projects/{project_id}/requirements",
        json={"requirements": "One-click autonomous build."},
    )
    launch_response = client.post(f"/api/projects/{project_id}/launch")
    assert launch_response.status_code == 200

    progress_response = client.get(f"/api/projects/{project_id}/progress")
    assert progress_response.status_code == 200
    payload = progress_response.json()
    assert payload["project_id"] == project_id
