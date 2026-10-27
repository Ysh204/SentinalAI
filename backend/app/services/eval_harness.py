"""Eval scenarios that must be classified from logs, not injector labels."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.models.incident import VerdictCategory
from backend.app.models.schemas import AlertCreate, IncidentPublic


@dataclass
class Scenario:
    name: str
    alert: AlertCreate
    expected_category: VerdictCategory
    expected_action: str | None


SCENARIOS: list[Scenario] = [
    Scenario(
        "Cart line TypeError",
        AlertCreate(
            source="sdk",
            title="Checkout 500 while pricing a cart line",
            error_message="TypeError: cannot subscript None in cart pricing",
            stack_trace=(
                'Traceback (most recent call last):\n'
                '  File "shop.py", line 200, in _run_checkout\n'
                '    total += _line_total(item)\n'
                '  File "shop.py", line 45, in _line_total\n'
                '    return int(item["price"]) * int(item["qty"])\n'
                "TypeError: 'NoneType' object is not subscriptable"
            ),
            endpoint="/checkout",
            status_code=500,
            logs=["checkout crash while summing line items", "order=ord-4412"],
            captured_request={"method": "POST", "path": "/checkout", "status_code": 500},
        ),
        VerdictCategory.CODE_BUG,
        "patch",
    ),
    Scenario(
        "Credential rejected at charge time",
        AlertCreate(
            source="sdk",
            title="Payments unauthorized",
            error_message="charge declined: unauthorized — token expired at 04:00 UTC",
            stack_trace="",
            endpoint="/checkout",
            status_code=401,
            logs=["payments processor returned 401", "key rotation window missed"],
            captured_request={"method": "POST", "path": "/checkout", "status_code": 401},
        ),
        VerdictCategory.CONFIG,
        "restore_config",
    ),
    Scenario(
        "Payments circuit open",
        AlertCreate(
            source="sdk",
            title="Charge processor unavailable",
            error_message="upstream charge processor circuit breaker is open",
            stack_trace="",
            endpoint="/checkout",
            status_code=503,
            logs=["14 timeouts to payment gateway in 2 min", "checkout http 503"],
            captured_request={"method": "POST", "path": "/checkout", "status_code": 503},
        ),
        VerdictCategory.DEPENDENCY_OUTAGE,
        "fallback",
    ),
    Scenario(
        "Regression right after release",
        AlertCreate(
            source="sdk",
            title="Paid orders 500 after new revision",
            error_message="unhandled exception in checkout handler after deploy",
            stack_trace="RuntimeError: checkout handler now raises on every paid order",
            endpoint="/checkout",
            status_code=500,
            logs=["error rate jumped immediately after the new revision", "last_deploy_diff: handler now raises"],
            captured_request={"method": "POST", "path": "/checkout", "status_code": 500},
        ),
        VerdictCategory.BAD_DEPLOY,
        "rollback",
    ),
    Scenario(
        "Heap exhaustion",
        AlertCreate(
            source="health_check",
            title="Checkout RSS climbed through the ceiling",
            error_message="MemoryError: checkout heap exhausted",
            stack_trace="",
            endpoint="/checkout",
            status_code=500,
            logs=["rss=2.4GB", "memory pressure on health check"],
            captured_request={"method": "POST", "path": "/checkout", "status_code": 500},
        ),
        VerdictCategory.RESOURCE,
        "restart",
    ),
    Scenario(
        "None cart line paraphrased",
        AlertCreate(
            source="webhook",
            title="Pricer crashed on a missing line",
            error_message="TypeError: 'NoneType' object is not subscriptable",
            stack_trace='File "shop.py", line 45, in _line_total',
            endpoint="/checkout",
            status_code=500,
            logs=["traceback in _line_total while iterating items"],
        ),
        VerdictCategory.CODE_BUG,
        "patch",
    ),
    Scenario(
        "Gateway 503 paraphrased",
        AlertCreate(
            source="webhook",
            title="Customers cannot pay",
            error_message="payments API unavailable from checkout",
            logs=["charge processor 503", "no matching deploy in the last 6h"],
            status_code=503,
        ),
        VerdictCategory.DEPENDENCY_OUTAGE,
        "fallback",
    ),
    Scenario(
        "Expired merchant key paraphrased",
        AlertCreate(
            source="webhook",
            title="Merchant key no longer accepted",
            error_message="Invalid API key expired for payments",
            status_code=401,
            logs=["unauthorized from payments"],
        ),
        VerdictCategory.CONFIG,
        "restore_config",
    ),
    Scenario(
        "Release rollback candidate paraphrased",
        AlertCreate(
            source="sdk",
            title="Spike started at the last checkout release",
            error_message="RuntimeError after deploy of the checkout handler",
            logs=["regression after release", "500s on every paid order"],
            status_code=500,
        ),
        VerdictCategory.BAD_DEPLOY,
        "rollback",
    ),
    Scenario(
        "Ambiguous brownout — must escalate",
        AlertCreate(
            source="pager",
            title="Occasional slowness",
            error_message="users report checkout feels slow this afternoon",
            stack_trace="",
            logs=["p95 latency up a bit", "no stack", "no status code"],
        ),
        VerdictCategory.UNKNOWN,
        None,
    ),
]


def score(incidents: list[tuple[Scenario, IncidentPublic]]) -> dict:
    correct = 0
    rows = []
    for scenario, incident in incidents:
        verdict = incident.verdict
        ok = bool(verdict and verdict.category == scenario.expected_category)
        if ok and scenario.expected_action:
            ok = verdict.recommended_action == scenario.expected_action
        if ok and scenario.expected_category == VerdictCategory.UNKNOWN:
            ok = bool(verdict and verdict.escalate_to_human)
        if ok:
            correct += 1
        rows.append(
            {
                "scenario": scenario.name,
                "expected": scenario.expected_category.value,
                "got": verdict.category.value if verdict else None,
                "action": verdict.recommended_action if verdict else None,
                "correct": ok,
                "note": "classified from alert logs only; injector failure_mode was not primed",
            }
        )
    return {
        "correct": correct,
        "total": len(incidents),
        "accuracy": f"{correct} out of {len(incidents)}",
        "rows": rows,
    }
