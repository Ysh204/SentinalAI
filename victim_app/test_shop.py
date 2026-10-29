from fastapi.testclient import TestClient

try:
    import state
    from main import app
except ImportError:
    from victim_app import state
    from victim_app.main import app


def setup_function() -> None:
    state.inject("none")


def test_checkout_ok() -> None:
    client = TestClient(app)
    response = client.post("/checkout")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_payments_outage_and_fallback() -> None:
    client = TestClient(app)
    client.post("/control/inject", json={"mode": "payments_outage"})
    down = client.post("/checkout")
    assert down.status_code == 503
    client.post("/control/fallback")
    recovered = client.post("/checkout")
    assert recovered.status_code == 200
    assert recovered.json()["charge"]["processor"] == "fallback-cod"


def test_checkout_handles_code_bug_or_null_item() -> None:
    client = TestClient(app)
    client.post("/control/inject", json={"mode": "code_bug"})
    response = client.post("/checkout")
    assert response.status_code == 200
    assert response.json()["ok"] is True
