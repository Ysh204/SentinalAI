from fastapi.testclient import TestClient

from victim_app import state


def test_alert_creates_and_triages_dependency_outage(client: TestClient) -> None:
    state.inject("payments_outage")
    response = client.post(
        "/api/alerts",
        json={
            "source": "sdk",
            "error_message": "Payments API unavailable",
            "status_code": 503,
            "endpoint": "/checkout",
            "logs": ["checkout http 503: Payments API unavailable"],
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["verdict"]["category"] == "dependency_outage"
    assert body["verdict"]["recommended_track"] == "mitigation"
    assert body["status"] == "MITIGATION_PROPOSED"
    assert body["mitigation"]["action"] == "fallback"
    assert body["mitigation"]["simulated"] is True


def test_duplicate_alerts_group(client: TestClient) -> None:
    payload = {
        "source": "sdk",
        "error_message": "Payments API unavailable",
        "fingerprint": "dup-test-1",
        "status_code": 503,
    }
    first = client.post("/api/alerts", json=payload)
    second = client.post("/api/alerts", json=payload)
    assert first.status_code == 201
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["occurrence_count"] == 2


def test_break_code_bug_then_patch_replay(client: TestClient) -> None:
    broken = client.post("/api/demo/break", json={"mode": "code_bug"})
    assert broken.status_code == 200
    body = broken.json()
    assert body["verdict"]["category"] == "code_bug"
    incident_id = body["id"]

    patched = client.post(f"/api/incidents/{incident_id}/generate-patch")
    assert patched.status_code == 200
    assert "if item is None" in patched.json()["proposed_patch"]

    validated = client.post(f"/api/incidents/{incident_id}/validate")
    assert validated.status_code == 200
    assert validated.json()["validation_results"]["overall_passed"] is True

    replayed = client.post(f"/api/incidents/{incident_id}/replay")
    assert replayed.status_code == 200
    replay = replayed.json()["replay"]
    assert replay["before_ok"] is False
    assert replay["after_ok"] is True
    assert replay["before_status"] >= 400
    assert replay["after_status"] < 400
    assert "HTTP" in replay["detail"]
    assert replayed.json()["status"] == "PATCH_VERIFIED"


def test_mitigation_fallback_without_code_change(client: TestClient) -> None:
    broken = client.post("/api/demo/break", json={"mode": "payments_outage"})
    incident_id = broken.json()["id"]
    assert broken.json()["status"] == "MITIGATION_PROPOSED"

    approved = client.post(
        f"/api/incidents/{incident_id}/approve",
        json={"actor": "tester", "note": "enable fallback"},
    )
    assert approved.status_code == 200
    body = approved.json()
    assert body["status"] == "MITIGATED"
    assert body["mitigation"]["action"] == "fallback"
    assert body["mitigation"]["recovered"] is True
    assert state.snapshot()["fallback_enabled"] is True

    report = client.post(f"/api/incidents/{incident_id}/postmortem")
    assert report.status_code == 200
    assert report.json()["postmortem"]["root_cause"] == "dependency_outage"


def test_eval_classifies_known_scenarios(client: TestClient) -> None:
    result = client.post("/api/eval/run")
    assert result.status_code == 200
    body = result.json()
    assert body["total"] == 10
    assert body["correct"] == body["total"]
    assert all(row["correct"] for row in body["rows"])


def test_metrics_endpoint(client: TestClient) -> None:
    client.post("/api/demo/simulate")
    response = client.get("/api/metrics")
    assert response.status_code == 200
    body = response.json()
    assert body["incidents_total"] >= 1
    assert "dependency_outage" in body["by_category"]
