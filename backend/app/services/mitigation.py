"""Simulated mitigation adapters against the demo shop control API."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

import httpx

from backend.app.core.config import Settings
from backend.app.core.exceptions import SentinelAIError
from backend.app.models.incident import VerdictCategory
from backend.app.models.schemas import IncidentPublic, MitigationRecord, Verdict

# Real Kubernetes / LaunchDarkly adapters would implement the same callables.
ACTIONS: dict[str, str] = {
    "rollback": "/control/rollback",
    "fallback": "/control/fallback",
    "disable_feature": "/control/disable-feature",
    "restart": "/control/restart",
    "restore_config": "/control/restore-config",
}

CATEGORY_ACTION = {
    VerdictCategory.DEPENDENCY_OUTAGE: "fallback",
    VerdictCategory.BAD_DEPLOY: "rollback",
    VerdictCategory.CONFIG: "restore_config",
    VerdictCategory.RESOURCE: "restart",
}


class MitigationService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def propose(self, incident: IncidentPublic) -> MitigationRecord:
        verdict = incident.verdict
        action = _action_for(verdict)
        before = self._error_rate()
        return MitigationRecord(
            action=action,
            simulated=True,
            status="proposed",
            error_rate_before=before,
            detail=(
                f"Simulated adapter would call shop {ACTIONS[action]}. "
                "This is a demo environment, not a production control plane."
            ),
        )

    def execute(self, incident: IncidentPublic, actor: str) -> MitigationRecord:
        record = incident.mitigation or self.propose(incident)
        before = record.error_rate_before if record.error_rate_before is not None else self._error_rate()
        self._call(record.action)
        after = self._error_rate(probe=True)
        recovered = after <= before or after < 0.2
        record.status = "executed"
        record.simulated = True
        record.executed_at = datetime.now(timezone.utc)
        record.actor = actor
        record.error_rate_before = before
        record.error_rate_after = after
        record.recovered = recovered
        record.detail = (
            f"Simulated {record.action} executed. Error rate {before} → {after}. "
            "Demo adapters only; production would plug into the same interface."
        )
        return record

    def _call(self, action: str) -> None:
        path = ACTIONS.get(action)
        if not path:
            raise SentinelAIError(f"Unknown mitigation action {action}.", code="unknown_action")
        url = self.settings.victim_app_url.rstrip("/")
        if url == "inline":
            _inline_action(action)
            return
        try:
            response = httpx.post(f"{url}{path}", timeout=3.0)
        except httpx.HTTPError as exc:
            raise SentinelAIError(
                f"Simulated adapter could not reach the demo shop: {exc}",
                code="victim_unreachable",
                status_code=502,
            ) from exc
        if response.status_code >= 400:
            raise SentinelAIError(
                f"Shop control API returned {response.status_code}.",
                code="mitigation_failed",
                status_code=502,
            )

    def _error_rate(self, probe: bool = False) -> float:
        url = self.settings.victim_app_url.rstrip("/")
        if url == "inline":
            from victim_app import state
            from victim_app.shop import SAMPLE_CART, _run_checkout

            if probe:
                try:
                    _run_checkout(dict(SAMPLE_CART))
                    state.record_result(True)
                except Exception:
                    state.record_result(False)
            return float(state.snapshot()["error_rate"])
        try:
            if probe:
                httpx.post(f"{url}/checkout", json={"order_id": "probe"}, timeout=3.0)
            metrics = httpx.get(f"{url}/metrics", timeout=2.0)
            if metrics.status_code == 200:
                return float(metrics.json().get("error_rate") or 0)
        except httpx.HTTPError:
            return 1.0
        return 0.0


def _action_for(verdict: Verdict | None) -> str:
    if verdict and verdict.recommended_action and verdict.recommended_action in ACTIONS:
        return verdict.recommended_action
    if verdict:
        return CATEGORY_ACTION.get(verdict.category, "restart")
    return "restart"


def _inline_action(action: str) -> None:
    from victim_app import state

    mapping: dict[str, Callable[[], Any]] = {
        "rollback": state.rollback,
        "fallback": state.enable_fallback,
        "disable_feature": state.disable_feature,
        "restart": state.restart,
        "restore_config": state.restore_config,
    }
    mapping[action]()
