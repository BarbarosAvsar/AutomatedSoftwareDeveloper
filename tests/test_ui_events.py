from fastapi.testclient import TestClient

from ui.backend.app import create_app


def test_launch_emits_websocket_events() -> None:
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

    with client.websocket_connect(f"/api/events/{project_id}/ws") as websocket:
        payload = websocket.receive_json()
        assert payload["event_type"] in {"policy_snapshot", "autonomy_launch", "agent_activity"}
        assert payload["project_id"] == project_id
