from fastapi.testclient import TestClient

try:
    import state
    from main import app
except ImportError:
    from victim_app import state
    from victim_app.main import app


def test_checkout_handles_code_bug_or_null_item() -> None:
    state.inject("none")
    client = TestClient(app)
    client.post("/control/inject", json={"mode": "code_bug"})
    response = client.post("/checkout")
    assert response.status_code == 200
    assert response.json()["ok"] is True

