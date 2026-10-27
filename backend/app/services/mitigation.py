"""Simulated mitigation adapters against the demo shop control API."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

import httpx

from backend.app.core.config import Settings
from backend.app.core.exceptions import SentinelAIError
from backend.app.models.incident import VerdictCategory
from backend.app.models.schemas import IncidentPublic, MitigationRecord, Verdict

PROBE_CART = {
    "order_id": "probe",
    "email": "probe@example.com",
    "card_number": "4242424242424242",
    "items": [{"sku": "mug", "price": 12, "qty": 1}],
}
PROBE_SAMPLES = 5
RECOVERY_ERROR_CEILING = 0.05

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
        after = self._probe_error_rate()
        recovered = after < before and after <= RECOVERY_ERROR_CEILING
        record.status = "executed"
        record.simulated = True
        record.executed_at = datetime.now(timezone.utc)
        record.actor = actor
        record.error_rate_before = before
        record.error_rate_after = after
        record.recovered = recovered
        record.detail = (
            f"Simulated {record.action} executed. Probe error rate {before} → {after}. "
            f"Recovered={recovered} (requires after < before and after ≤ {RECOVERY_ERROR_CEILING}). "
            "Demo adapters only; production would plug into the same interface."
        )
        return record

    def _shop_url(self) -> str:
        return self.settings.victim_app_url.rstrip("/")

    def _is_inline(self) -> bool:
        return self._shop_url() == "inline"

    def _call(self, action: str) -> None:
        path = ACTIONS.get(action)
        if not path:
            raise SentinelAIError(f"Unknown mitigation action {action}.", code="unknown_action")
        if self._is_inline():
            _inline_action(action)
            return
        url = self._shop_url()
        try:
            response = httpx.post(f"{url}{path}", timeout=httpx.Timeout(2.0, connect=0.2))
        except httpx.HTTPError as exc:
            raise SentinelAIError(
                f"Victim app is unreachable at {url}; mitigation was not executed.",
                code="victim_unreachable",
                status_code=503,
            ) from exc
        if response.status_code >= 400:
            raise SentinelAIError(
                f"Shop control API returned {response.status_code}.",
                code="mitigation_failed",
                status_code=502,
            )

    def _error_rate(self) -> float:
        if self._is_inline():
            from victim_app import state

            return float(state.snapshot()["error_rate"])
        url = self._shop_url()
        try:
            metrics = httpx.get(f"{url}/metrics", timeout=httpx.Timeout(1.5, connect=0.2))
        except httpx.HTTPError as exc:
            raise SentinelAIError(
                f"Victim app is unreachable at {url}; cannot read error rate.",
                code="victim_unreachable",
                status_code=503,
            ) from exc
        if metrics.status_code != 200:
            raise SentinelAIError(
                f"Shop metrics returned HTTP {metrics.status_code}.",
                code="victim_unreachable",
                status_code=503,
            )
        return float(metrics.json().get("error_rate") or 0)

    def _probe_error_rate(self, samples: int = PROBE_SAMPLES) -> float:
        failures = 0
        for _ in range(samples):
            if not self._checkout_ok():
                failures += 1
        return round(failures / samples, 4)

    def _checkout_ok(self) -> bool:
        if self._is_inline():
            from victim_app.shop import SAMPLE_CART, _run_checkout

            try:
                _run_checkout(dict(SAMPLE_CART))
                return True
            except Exception:
                return False
        url = self._shop_url()
        try:
            response = httpx.post(
                f"{url}/checkout",
                json=PROBE_CART,
                timeout=httpx.Timeout(1.5, connect=0.2),
            )
        except httpx.HTTPError as exc:
            raise SentinelAIError(
                f"Victim app is unreachable at {url}; cannot probe checkout.",
                code="victim_unreachable",
                status_code=503,
            ) from exc
        return response.status_code < 400


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
