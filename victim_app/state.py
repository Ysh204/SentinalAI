"""Mutable shop state. Failure injection and simulated ops live here."""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import Any

_lock = threading.Lock()

_STATE: dict[str, Any] = {
    "failure_mode": "none",
    "fallback_enabled": False,
    "feature_checkout_enabled": True,
    "healthy": True,
    "deploy_version": "good-1.0.0",
    "previous_version": "good-1.0.0",
    "last_deploy_at": datetime.now(UTC).isoformat(),
    "last_deploy_diff": "baseline checkout handler",
    "payments_api_key": "live-ok-key",
    "memory_sink": [],
    "logs": [],
    "error_count": 0,
    "ok_count": 0,
    "restart_count": 0,
}


def snapshot() -> dict[str, Any]:
    with _lock:
        sink = _STATE["memory_sink"]
        logs = list(_STATE["logs"][-80:])
        return {
            "failure_mode": _STATE["failure_mode"],
            "fallback_enabled": _STATE["fallback_enabled"],
            "feature_checkout_enabled": _STATE["feature_checkout_enabled"],
            "healthy": _STATE["healthy"],
            "deploy_version": _STATE["deploy_version"],
            "previous_version": _STATE["previous_version"],
            "last_deploy_at": _STATE["last_deploy_at"],
            "last_deploy_diff": _STATE["last_deploy_diff"],
            "payments_api_key_status": (
                "expired" if str(_STATE["payments_api_key"]).startswith("expired") else "valid"
            ),
            "memory_bytes": sum(len(chunk) for chunk in sink),
            "logs": logs,
            "error_count": _STATE["error_count"],
            "ok_count": _STATE["ok_count"],
            "restart_count": _STATE["restart_count"],
            "error_rate": _error_rate_unlocked(),
        }


def _error_rate_unlocked() -> float:
    total = int(_STATE["error_count"]) + int(_STATE["ok_count"])
    if total <= 0:
        return 0.0
    return round(int(_STATE["error_count"]) / total, 4)


def get(key: str) -> Any:
    with _lock:
        return _STATE[key]


def set_value(key: str, value: Any) -> None:
    with _lock:
        _STATE[key] = value


def record_result(ok: bool) -> None:
    with _lock:
        if ok:
            _STATE["ok_count"] += 1
        else:
            _STATE["error_count"] += 1


def append_log(line: str) -> None:
    with _lock:
        _STATE["logs"].append(f"{datetime.now(UTC).isoformat()} {line}")
        if len(_STATE["logs"]) > 400:
            _STATE["logs"] = _STATE["logs"][-200:]


def leak_memory() -> int:
    with _lock:
        _STATE["memory_sink"].append(b"x" * 256_000)
        if len(_STATE["memory_sink"]) > 80:
            _STATE["memory_sink"] = _STATE["memory_sink"][-80:]
        return sum(len(chunk) for chunk in _STATE["memory_sink"])


def reset_memory() -> None:
    with _lock:
        _STATE["memory_sink"] = []


def inject(mode: str) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    with _lock:
        _STATE["failure_mode"] = mode
        _STATE["healthy"] = True
        _STATE["fallback_enabled"] = False
        _STATE["feature_checkout_enabled"] = True
        _STATE["error_count"] = 0
        _STATE["ok_count"] = 0
        if mode == "expired_key":
            _STATE["payments_api_key"] = "expired-key"
        else:
            _STATE["payments_api_key"] = "live-ok-key"
        if mode == "bad_deploy":
            _STATE["previous_version"] = _STATE["deploy_version"]
            _STATE["deploy_version"] = "bad-2.0.0"
            _STATE["last_deploy_at"] = now
            _STATE["last_deploy_diff"] = (
                "checkout handler now raises RuntimeError on every paid order"
            )
        elif mode == "none":
            _STATE["deploy_version"] = "good-1.0.0"
            _STATE["last_deploy_diff"] = "baseline checkout handler"
            _STATE["last_deploy_at"] = now
            _STATE["memory_sink"] = []
        if mode == "crash":
            _STATE["healthy"] = False
    append_log(f"injected failure_mode={mode}")
    return snapshot()


def rollback() -> dict[str, Any]:
    with _lock:
        _STATE["deploy_version"] = _STATE["previous_version"] or "good-1.0.0"
        _STATE["failure_mode"] = "none"
        _STATE["last_deploy_diff"] = "rolled back to previous known-good deploy"
        _STATE["last_deploy_at"] = datetime.now(UTC).isoformat()
        _STATE["healthy"] = True
    append_log("control: rollback executed")
    return snapshot()


def enable_fallback() -> dict[str, Any]:
    with _lock:
        _STATE["fallback_enabled"] = True
    append_log("control: payments fallback enabled")
    return snapshot()


def disable_feature() -> dict[str, Any]:
    with _lock:
        _STATE["feature_checkout_enabled"] = False
    append_log("control: checkout feature flag disabled")
    return snapshot()


def restart() -> dict[str, Any]:
    with _lock:
        _STATE["memory_sink"] = []
        _STATE["restart_count"] += 1
        _STATE["healthy"] = True
        if _STATE["failure_mode"] == "memory_leak":
            _STATE["failure_mode"] = "none"
        if _STATE["failure_mode"] == "crash":
            _STATE["failure_mode"] = "none"
    append_log("control: process restart simulated")
    return snapshot()


def restore_config() -> dict[str, Any]:
    with _lock:
        _STATE["payments_api_key"] = "live-ok-key"
        if _STATE["failure_mode"] == "expired_key":
            _STATE["failure_mode"] = "none"
    append_log("control: payments API key restored")
    return snapshot()
