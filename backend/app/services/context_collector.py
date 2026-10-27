"""Gather logs, deploy, config, and dependency health for triage."""

from __future__ import annotations

from typing import Any

import httpx

from backend.app.core.config import Settings
from backend.app.models.schemas import IncidentPublic
from backend.app.services.triage_rules import observable_victim


class ContextCollector:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def collect(self, incident: IncidentPublic) -> dict[str, Any]:
        context: dict[str, Any] = {
            "incident_title": incident.title,
            "error_message": incident.error_message,
            "stack_trace": incident.stack_trace,
            "source": incident.source,
            "captured_request": incident.captured_request,
            "incident_logs": incident.logs[-30:],
            "victim": None,
            "collector_error": None,
        }
        url = self.settings.victim_app_url.rstrip("/")
        if url == "inline":
            context["victim"] = observable_victim(_inline_victim_context())
            return context
        try:
            response = httpx.get(f"{url}/control/context", timeout=httpx.Timeout(1.0, connect=0.2))
        except httpx.HTTPError as exc:
            context["collector_error"] = f"victim app unreachable ({exc})"
            return context
        if response.status_code == 200:
            context["victim"] = observable_victim(response.json())
        else:
            context["collector_error"] = f"victim context HTTP {response.status_code}"
        return context


def _inline_victim_context() -> dict[str, Any]:
    from victim_app import state

    snap = state.snapshot()
    payments = "down" if snap["failure_mode"] == "payments_outage" and not snap["fallback_enabled"] else "up"
    if snap["failure_mode"] == "expired_key":
        payments = "auth_failed"
    return {
        "service": "checkout",
        "deploy_version": snap["deploy_version"],
        "last_deploy_at": snap["last_deploy_at"],
        "last_deploy_diff": snap["last_deploy_diff"],
        "config": {
            "payments_api_key_status": snap["payments_api_key_status"],
            "fallback_enabled": snap["fallback_enabled"],
            "feature_checkout_enabled": snap["feature_checkout_enabled"],
        },
        "dependency_health": {"payments": payments},
        "recent_logs": snap["logs"][-30:],
        "error_rate": snap["error_rate"],
        "memory_bytes": snap["memory_bytes"],
        "healthy": snap["healthy"],
    }
