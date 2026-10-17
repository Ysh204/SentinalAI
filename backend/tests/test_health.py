from fastapi.testclient import TestClient


def test_health_ok_without_api_key(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"] == "SentinelAI"
    assert body["team"] == "Team TriNova"
    assert body["ai_provider"] == "mock"
    assert body["gemini_configured"] is False
    assert body["database_ready"] is True
