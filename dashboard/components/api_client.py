from __future__ import annotations

import os

import httpx

DEFAULT_BACKEND = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")


class BackendError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class SentinelAPI:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or DEFAULT_BACKEND).rstrip("/")

    def _request(self, method: str, path: str, json: dict | None = None) -> dict | list:
        url = f"{self.base_url}{path}"
        try:
            response = httpx.request(method, url, json=json, timeout=60.0)
        except httpx.ConnectError as exc:
            raise BackendError(
                f"Cannot reach SentinelAI backend at {self.base_url}. Start uvicorn first."
            ) from exc
        if response.status_code >= 400:
            detail = response.text
            try:
                payload = response.json()
                detail = payload.get("detail", detail)
            except ValueError:
                pass
            raise BackendError(str(detail), status_code=response.status_code)
        if not response.content:
            return {}
        return response.json()

    def health(self) -> dict:
        return self._request("GET", "/health")  # type: ignore[return-value]

    def list_incidents(self) -> list[dict]:
        return self._request("GET", "/api/incidents")  # type: ignore[return-value]

    def get_incident(self, incident_id: str) -> dict:
        return self._request("GET", f"/api/incidents/{incident_id}")  # type: ignore[return-value]

    def create_incident(self, payload: dict) -> dict:
        return self._request("POST", "/api/incidents", json=payload)  # type: ignore[return-value]

    def analyze(self, incident_id: str) -> dict:
        return self._request("POST", f"/api/incidents/{incident_id}/analyze")  # type: ignore[return-value]

    def generate_patch(self, incident_id: str) -> dict:
        return self._request("POST", f"/api/incidents/{incident_id}/generate-patch")  # type: ignore[return-value]

    def validate(self, incident_id: str) -> dict:
        return self._request("POST", f"/api/incidents/{incident_id}/validate")  # type: ignore[return-value]

    def approve(self, incident_id: str) -> dict:
        return self._request("POST", f"/api/incidents/{incident_id}/approve", json={})  # type: ignore[return-value]

    def reject(self, incident_id: str, reason: str) -> dict:
        return self._request(
            "POST",
            f"/api/incidents/{incident_id}/reject",
            json={"reason": reason, "actor": "dashboard-user"},
        )  # type: ignore[return-value]
