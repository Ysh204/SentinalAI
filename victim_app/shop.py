"""Checkout routes with five injectable failures."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

try:
    from victim_app import state
    from victim_app.redact import redact
    from victim_app.sdk import format_exc, report_error
except ImportError:
    import state
    from redact import redact
    from sdk import format_exc, report_error

router = APIRouter()

SAMPLE_CART = {
    "order_id": "ord-1001",
    "email": "customer@example.com",
    "card_number": "4242424242424242",
    "items": [{"sku": "mug", "price": 12, "qty": 1}],
}


class CheckoutBody(BaseModel):
    order_id: str = "ord-1001"
    email: str = "customer@example.com"
    card_number: str = "4242424242424242"
    items: list[dict[str, Any]] = Field(default_factory=lambda: [{"sku": "mug", "price": 12, "qty": 1}])


class InjectBody(BaseModel):
    mode: str = Field(
        ...,
        description="none | code_bug | expired_key | payments_outage | bad_deploy | memory_leak | crash",
    )


def _line_total(item: dict[str, Any] | None) -> int:
    # Intentional crash site for the code_bug injector: item may be None.
    return int(item["price"]) * int(item["qty"])


def _charge_payments(amount: int) -> dict[str, Any]:
    mode = state.get("failure_mode")
    key = str(state.get("payments_api_key"))
    if mode == "expired_key" or key.startswith("expired"):
        raise HTTPException(status_code=401, detail="Payments API key expired")
    if mode == "payments_outage":
        if state.get("fallback_enabled"):
            return {"processor": "fallback-cod", "status": "accepted", "amount": amount}
        raise HTTPException(status_code=503, detail="Payments API unavailable")
    return {"processor": "payments", "status": "charged", "amount": amount}


@router.get("/health")
def health() -> dict[str, Any]:
    snap = state.snapshot()
    if not snap["healthy"]:
        raise HTTPException(status_code=503, detail="shop process is not responding")
    if snap["failure_mode"] == "memory_leak" and snap["memory_bytes"] > 2_000_000:
        raise HTTPException(status_code=503, detail="memory pressure")
    return {"status": "ok", "service": "checkout", "version": snap["deploy_version"]}


@router.get("/metrics")
def metrics() -> dict[str, Any]:
    snap = state.snapshot()
    return {
        "error_rate": snap["error_rate"],
        "error_count": snap["error_count"],
        "ok_count": snap["ok_count"],
        "memory_bytes": snap["memory_bytes"],
    }


@router.get("/control/context")
def control_context() -> dict[str, Any]:
    snap = state.snapshot()
    payments = "down" if snap["failure_mode"] == "payments_outage" and not snap["fallback_enabled"] else "up"
    if snap["failure_mode"] == "expired_key":
        payments = "auth_failed"
    return {
        "service": "checkout",
        "failure_mode": snap["failure_mode"],
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


@router.post("/control/inject")
def control_inject(body: InjectBody) -> dict[str, Any]:
    allowed = {
        "none",
        "code_bug",
        "expired_key",
        "payments_outage",
        "bad_deploy",
        "memory_leak",
        "crash",
    }
    if body.mode not in allowed:
        raise HTTPException(status_code=400, detail=f"Unknown mode {body.mode}")
    return state.inject(body.mode)


@router.post("/control/rollback")
def control_rollback() -> dict[str, Any]:
    return state.rollback()


@router.post("/control/fallback")
def control_fallback() -> dict[str, Any]:
    return state.enable_fallback()


@router.post("/control/disable-feature")
def control_disable_feature() -> dict[str, Any]:
    return state.disable_feature()


@router.post("/control/restart")
def control_restart() -> dict[str, Any]:
    return state.restart()


@router.post("/control/restore-config")
def control_restore_config() -> dict[str, Any]:
    return state.restore_config()


@router.post("/checkout")
async def checkout(request: Request, body: CheckoutBody | None = None) -> dict[str, Any]:
    payload = body.model_dump() if body else SAMPLE_CART
    state.append_log(f"checkout attempt order={payload.get('order_id')}")
    captured = {"method": "POST", "path": "/checkout", "body": redact(payload)}
    try:
        result = _run_checkout(payload)
        state.record_result(True)
        state.append_log("checkout ok")
        return result
    except HTTPException as exc:
        state.record_result(False)
        state.append_log(f"checkout http {exc.status_code}: {exc.detail}")
        report_error(
            error=str(exc.detail),
            stack_trace=format_exc(),
            endpoint="/checkout",
            status_code=exc.status_code,
            captured_request=captured,
            logs=state.snapshot()["logs"],
        )
        raise
    except Exception as exc:
        state.record_result(False)
        stack = format_exc()
        state.append_log(f"checkout crash: {exc}")
        report_error(
            error=str(exc),
            stack_trace=stack,
            endpoint="/checkout",
            status_code=500,
            captured_request=captured,
            logs=state.snapshot()["logs"],
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _run_checkout(payload: dict[str, Any]) -> dict[str, Any]:
    if not state.get("feature_checkout_enabled"):
        raise HTTPException(status_code=503, detail="Checkout feature flag disabled")
    mode = state.get("failure_mode")
    if mode == "memory_leak":
        used = state.leak_memory()
        state.append_log(f"memory_sink_bytes={used}")
        if used > 2_000_000:
            raise HTTPException(status_code=500, detail="MemoryError: checkout heap exhausted")
    if mode == "bad_deploy":
        raise RuntimeError("unhandled exception in checkout handler after deploy bad-2.0.0")
    items = list(payload.get("items") or [])
    if mode == "code_bug":
        items = [None, *items]  # type: ignore[list-item]
    total = 0
    for item in items:
        total += _line_total(item)
    charge = _charge_payments(total)
    return {"ok": True, "total": total, "charge": charge, "order_id": payload.get("order_id")}
