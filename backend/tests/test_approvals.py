from fastapi.testclient import TestClient

from backend.tests.conftest import SAMPLE_PAYLOAD


def _create(client: TestClient) -> str:
    return client.post("/api/incidents", json=SAMPLE_PAYLOAD).json()["id"]


def test_approval_before_validation_is_rejected(client: TestClient) -> None:
    incident_id = _create(client)
    response = client.post(f"/api/incidents/{incident_id}/approve")
    assert response.status_code == 409
    assert "status" in response.json()["detail"].lower() or "validat" in response.json()["detail"].lower()


def test_approval_after_failed_validation_is_rejected(client: TestClient) -> None:
    incident_id = _create(client)
    assert client.post(f"/api/incidents/{incident_id}/analyze").status_code == 200
    assert client.post(f"/api/incidents/{incident_id}/generate-patch").status_code == 200

    from backend.tests.conftest import BAD_PATCH

    service = client.app.state.container.incidents
    incident = service.get(incident_id)
    incident.proposed_patch = BAD_PATCH
    service.repository.save(incident)

    validated = client.post(f"/api/incidents/{incident_id}/validate")
    assert validated.status_code == 200
    body = validated.json()
    assert body["status"] == "VALIDATION_FAILED"
    assert body["validation_results"]["overall_passed"] is False

    approve = client.post(f"/api/incidents/{incident_id}/approve")
    assert approve.status_code == 409


def test_rejection_records_reason(client: TestClient) -> None:
    incident_id = _create(client)
    analyzed = client.post(f"/api/incidents/{incident_id}/analyze")
    assert analyzed.status_code == 200
    rejected = client.post(
        f"/api/incidents/{incident_id}/reject",
        json={"reason": "Need more evidence before patching."},
    )
    assert rejected.status_code == 200
    body = rejected.json()
    assert body["status"] == "REJECTED"
    assert body["approval"]["decision"] == "rejected"
    assert "evidence" in body["approval"]["reason"]
