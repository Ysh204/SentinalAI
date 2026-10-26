"""Fixed demo scenarios with known expected verdicts."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.models.incident import VerdictCategory
from backend.app.models.schemas import AlertCreate, IncidentPublic


@dataclass
class Scenario:
    name: str
    mode: str
    alert: AlertCreate
    expected_category: VerdictCategory
    expected_action: str


SCENARIOS: list[Scenario] = [
    Scenario(
        "Null-pointer in checkout",
        "code_bug",
        AlertCreate(
            source="sdk",
            title="Null-pointer in checkout",
            error_message="'NoneType' object is not subscriptable",
            stack_trace='File "shop.py", line 45, in _line_total\n    return int(item["price"]) * int(item["qty"])',
            endpoint="/checkout",
            status_code=500,
            logs=["checkout crash: NoneType"],
        ),
        VerdictCategory.CODE_BUG,
        "patch",
    ),
    Scenario(
        "Expired API key",
        "expired_key",
        AlertCreate(
            source="sdk",
            title="Expired API key",
            error_message="Payments API key expired",
            stack_trace="",
            endpoint="/checkout",
            status_code=401,
            logs=["checkout http 401: Payments API key expired"],
        ),
        VerdictCategory.CONFIG,
        "restore_config",
    ),
    Scenario(
        "Payments API 503",
        "payments_outage",
        AlertCreate(
            source="sdk",
            title="Payments API 503",
            error_message="Payments API unavailable",
            stack_trace="",
            endpoint="/checkout",
            status_code=503,
            logs=["checkout http 503: Payments API unavailable"],
        ),
        VerdictCategory.DEPENDENCY_OUTAGE,
        "fallback",
    ),
    Scenario(
        "Bad deploy raises 500s",
        "bad_deploy",
        AlertCreate(
            source="sdk",
            title="Bad deploy raises 500s",
            error_message="unhandled exception in checkout handler after deploy bad-2.0.0",
            stack_trace="RuntimeError: after deploy bad-2.0.0",
            endpoint="/checkout",
            status_code=500,
            logs=["last deploy: checkout handler now raises RuntimeError"],
        ),
        VerdictCategory.BAD_DEPLOY,
        "rollback",
    ),
    Scenario(
        "Memory leak",
        "memory_leak",
        AlertCreate(
            source="sdk",
            title="Memory leak",
            error_message="MemoryError: checkout heap exhausted",
            stack_trace="",
            endpoint="/checkout",
            status_code=500,
            logs=["memory_sink_bytes=2500000", "memory pressure"],
        ),
        VerdictCategory.RESOURCE,
        "restart",
    ),
    Scenario(
        "Checkout NoneType variant",
        "code_bug",
        AlertCreate(
            source="webhook",
            title="Checkout NoneType variant",
            error_message="TypeError: 'NoneType' object is not subscriptable in _line_total",
            stack_trace="shop.py _line_total",
            endpoint="/checkout",
            status_code=500,
        ),
        VerdictCategory.CODE_BUG,
        "patch",
    ),
    Scenario(
        "Payments timeouts",
        "payments_outage",
        AlertCreate(
            source="webhook",
            title="Payments timeouts",
            error_message="14 timeouts to payments API in 2 min",
            stack_trace="",
            logs=["payments api unavailable", "503"],
            status_code=503,
        ),
        VerdictCategory.DEPENDENCY_OUTAGE,
        "fallback",
    ),
    Scenario(
        "Key rotation missed",
        "expired_key",
        AlertCreate(
            source="webhook",
            title="Key rotation missed",
            error_message="Invalid API key expired for payments",
            status_code=401,
        ),
        VerdictCategory.CONFIG,
        "restore_config",
    ),
    Scenario(
        "Deploy rollback candidate",
        "bad_deploy",
        AlertCreate(
            source="sdk",
            title="Deploy rollback candidate",
            error_message="500s after deploy bad-2.0.0",
            logs=["deploy_version=bad-2.0.0"],
        ),
        VerdictCategory.BAD_DEPLOY,
        "rollback",
    ),
    Scenario(
        "Heap climb",
        "memory_leak",
        AlertCreate(
            source="health_check",
            title="Heap climb",
            error_message="health check reports memory pressure",
            logs=["MemoryError"],
        ),
        VerdictCategory.RESOURCE,
        "restart",
    ),
]


def score(incidents: list[tuple[Scenario, IncidentPublic]]) -> dict:
    correct = 0
    rows = []
    for scenario, incident in incidents:
        verdict = incident.verdict
        ok = bool(verdict and verdict.category == scenario.expected_category)
        if ok:
            correct += 1
        rows.append(
            {
                "scenario": scenario.name,
                "expected": scenario.expected_category.value,
                "got": verdict.category.value if verdict else None,
                "correct": ok,
            }
        )
    return {"correct": correct, "total": len(incidents), "accuracy": f"{correct} out of {len(incidents)}", "rows": rows}
