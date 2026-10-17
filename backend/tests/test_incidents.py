from fastapi.testclient import TestClient

from backend.app.db.database import Database
from backend.app.repositories.incident_repository import IncidentRepository
from backend.tests.conftest import SAMPLE_PAYLOAD


def test_create_and_get_incident(client: TestClient) -> None:
    created = client.post("/api/incidents", json=SAMPLE_PAYLOAD)
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "RECEIVED"
    assert body["title"] == SAMPLE_PAYLOAD["title"]
    incident_id = body["id"]

    fetched = client.get(f"/api/incidents/{incident_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == incident_id

    listed = client.get("/api/incidents")
    assert listed.status_code == 200
    assert any(item["id"] == incident_id for item in listed.json())


def test_create_rejects_empty_title(client: TestClient) -> None:
    payload = {**SAMPLE_PAYLOAD, "title": ""}
    response = client.post("/api/incidents", json=payload)
    assert response.status_code == 422


def test_missing_incident_returns_404(client: TestClient) -> None:
    response = client.get("/api/incidents/does-not-exist")
    assert response.status_code == 404


def test_sqlite_persistence(tmp_settings) -> None:
    from fastapi.testclient import TestClient as FastClient

    from backend.app.api.deps import build_container
    from backend.app.main import create_app

    container = build_container(tmp_settings)
    client = FastClient(create_app(tmp_settings, container))
    created = client.post("/api/incidents", json=SAMPLE_PAYLOAD)
    incident_id = created.json()["id"]

    other_db = Database(tmp_settings.database_path)
    repo = IncidentRepository(other_db)
    loaded = repo.get(incident_id)
    assert loaded is not None
    assert loaded.title == SAMPLE_PAYLOAD["title"]
    assert loaded.status.value == "RECEIVED"
