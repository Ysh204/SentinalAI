"""Tiny in-app reporter. If checkout throws, this posts an alert to SentinelAI."""

from __future__ import annotations

import os
import threading
import traceback
from datetime import datetime, timezone
from typing import Any

import httpx

try:
    from victim_app.redact import redact
    from victim_app.state import append_log
except ImportError:
    from redact import redact
    from state import append_log

SENTINEL_ALERTS_URL = os.getenv("SENTINEL_ALERTS_URL", "http://127.0.0.1:8000/api/alerts")


def report_error(
    *,
    error: str,
    stack_trace: str,
    endpoint: str,
    status_code: int,
    captured_request: dict[str, Any] | None,
    logs: list[str],
) -> None:
    captured = redact(captured_request or {})
    if isinstance(captured, dict):
        captured.setdefault("status_code", status_code)
        captured.setdefault("path", endpoint)
    payload = {
        "source": "sdk",
        "service": "checkout",
        "title": f"Checkout failure: {error[:80]}",
        "error_message": error,
        "stack_trace": stack_trace,
        "endpoint": endpoint,
        "status_code": status_code,
        "captured_request": captured,
        "logs": logs[-20:],
        "repository_path": "victim_app",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
    }

    def _send() -> None:
        try:
            httpx.post(SENTINEL_ALERTS_URL, json=payload, timeout=2.0)
        except Exception as exc:  # noqa: BLE001 — reporting must never take down checkout
            append_log(f"sdk alert failed: {exc}")

    threading.Thread(target=_send, daemon=True).start()


def format_exc() -> str:
    return traceback.format_exc()
