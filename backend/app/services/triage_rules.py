"""Deterministic triage from observable logs and telemetry — never injector labels."""

from __future__ import annotations

from typing import Any

from backend.app.models.incident import RecommendedTrack, VerdictCategory
from backend.app.models.schemas import IncidentPublic, Verdict

LOW_CONFIDENCE = 0.55


def observable_victim(context: dict[str, Any]) -> dict[str, Any]:
    victim = dict(context.get("victim") or {})
    victim.pop("failure_mode", None)
    logs = []
    for line in victim.get("recent_logs") or []:
        text = str(line)
        if "injected failure_mode=" in text:
            continue
        logs.append(line)
    victim["recent_logs"] = logs
    return victim


def _blob(incident: IncidentPublic, context: dict[str, Any]) -> str:
    victim = observable_victim(context)
    config = victim.get("config") or {}
    deps = victim.get("dependency_health") or {}
    parts = [
        incident.title,
        incident.error_message,
        incident.stack_trace,
        " ".join(incident.logs[-20:]),
        str(victim.get("last_deploy_diff") or ""),
        str(victim.get("deploy_version") or ""),
        str(config.get("payments_api_key_status") or ""),
        str(deps.get("payments") or ""),
        " ".join(str(line) for line in (victim.get("recent_logs") or [])[-20:]),
        str(context.get("collector_error") or ""),
    ]
    return " ".join(parts).lower()


def classify(incident: IncidentPublic, context: dict[str, Any], provider: str) -> Verdict:
    text = _blob(incident, context)
    victim = observable_victim(context)
    status = incident.captured_request.get("status_code") if isinstance(incident.captured_request, dict) else None
    config = victim.get("config") or {}
    payments = str((victim.get("dependency_health") or {}).get("payments") or "").lower()
    key_status = str(config.get("payments_api_key_status") or "").lower()
    memory_bytes = victim.get("memory_bytes")
    try:
        memory_bytes = int(memory_bytes) if memory_bytes is not None else 0
    except (TypeError, ValueError):
        memory_bytes = 0

    if _looks_like_code_bug(text, incident):
        return Verdict(
            category=VerdictCategory.CODE_BUG,
            confidence=0.9,
            evidence=_evidence(
                "Application stack raised TypeError/AttributeError in shop code",
                incident.stack_trace or incident.error_message,
            ),
            recommended_track=RecommendedTrack.CODE_FIX,
            escalate_to_human=False,
            recommended_action="patch",
            provider=provider,
        )
    if _looks_like_expired_key(text, status, key_status, payments):
        return Verdict(
            category=VerdictCategory.CONFIG,
            confidence=0.88,
            evidence=_evidence(
                "Payments rejected the configured credential (401/expired/invalid key)",
                f"key_status={key_status or 'unknown'}",
            ),
            recommended_track=RecommendedTrack.MITIGATION,
            escalate_to_human=False,
            recommended_action="restore_config",
            provider=provider,
        )
    if _looks_like_dependency_outage(text, status, payments):
        return Verdict(
            category=VerdictCategory.DEPENDENCY_OUTAGE,
            confidence=0.84,
            evidence=_evidence(
                "Checkout failed because the payments dependency is down or timing out",
                f"dependency_health.payments={payments or 'unknown'}",
            ),
            recommended_track=RecommendedTrack.MITIGATION,
            escalate_to_human=False,
            recommended_action="fallback",
            provider=provider,
        )
    if _looks_like_bad_deploy(text, victim):
        return Verdict(
            category=VerdictCategory.BAD_DEPLOY,
            confidence=0.86,
            evidence=_evidence(
                "Failure tracks a recent checkout deploy whose diff changes request handling",
                str(victim.get("last_deploy_diff") or incident.error_message),
            ),
            recommended_track=RecommendedTrack.MITIGATION,
            escalate_to_human=False,
            recommended_action="rollback",
            provider=provider,
        )
    if _looks_like_resource(text, memory_bytes, victim):
        return Verdict(
            category=VerdictCategory.RESOURCE,
            confidence=0.85,
            evidence=_evidence(
                "Process is under memory/health pressure rather than a logic bug",
                f"memory_bytes={memory_bytes}",
            ),
            recommended_track=RecommendedTrack.MITIGATION,
            escalate_to_human=False,
            recommended_action="restart",
            provider=provider,
        )

    return Verdict(
        category=VerdictCategory.UNKNOWN,
        confidence=0.2,
        evidence=["Not enough observable signal to classify this failure"],
        recommended_track=RecommendedTrack.ESCALATE,
        escalate_to_human=True,
        recommended_action=None,
        provider=provider,
    )


def apply_confidence_gate(verdict: Verdict) -> Verdict:
    if verdict.confidence < LOW_CONFIDENCE:
        verdict.recommended_track = RecommendedTrack.ESCALATE
        verdict.escalate_to_human = True
        verdict.recommended_action = None
    return verdict


def _looks_like_code_bug(text: str, incident: IncidentPublic) -> bool:
    stack = (incident.stack_trace or "").lower()
    error = (incident.error_message or "").lower()
    in_app = any(token in stack or token in text for token in ("shop.py", "_line_total", "victim_app"))
    type_error = any(
        token in error or token in stack or token in text
        for token in (
            "typeerror",
            "attributeerror",
            "nonetype",
            "none type",
            "not subscriptable",
            "cannot subscript",
            "unsupported operand",
            "'none'",
        )
    )
    return type_error and (in_app or "traceback" in stack or "file \"" in stack or "_line_total" in text)


def _looks_like_expired_key(text: str, status: object, key_status: str, payments: str) -> bool:
    if key_status in {"expired", "invalid"} or payments == "auth_failed":
        return True
    auth = any(
        token in text
        for token in (
            "unauthorized",
            "invalid api key",
            "api key expired",
            "expired credential",
            "token expired",
            "key rotation",
            "401",
        )
    )
    try:
        code = int(status) if status is not None else None
    except (TypeError, ValueError):
        code = None
    return auth or code == 401


def _looks_like_dependency_outage(text: str, status: object, payments: str) -> bool:
    if payments in {"down", "unavailable"}:
        return True
    try:
        code = int(status) if status is not None else None
    except (TypeError, ValueError):
        code = None
    dependency = any(
        token in text
        for token in (
            "payments api",
            "payment gateway",
            "charge processor",
            "upstream",
            "circuit breaker",
            "timed out",
            "timeouts to payment",
            "503",
            "unavailable",
        )
    )
    return dependency and (
        code in {502, 503, 504}
        or "503" in text
        or "timeout" in text
        or "unavailable" in text
        or payments == "down"
    )


def _looks_like_bad_deploy(text: str, victim: dict[str, Any]) -> bool:
    diff = str(victim.get("last_deploy_diff") or "").lower()
    deploy_signal = any(
        token in text or token in diff
        for token in (
            "after deploy",
            "new revision",
            "handler now raises",
            "every paid order",
            "introduced in",
            "regression after release",
        )
    )
    runtime = "runtimeerror" in text or "unhandled exception" in text
    return bool(deploy_signal and (runtime or "500" in text or "error rate" in text))


def _looks_like_resource(text: str, memory_bytes: int, victim: dict[str, Any]) -> bool:
    if memory_bytes > 2_000_000:
        return True
    if victim.get("healthy") is False:
        return True
    return any(
        token in text
        for token in (
            "memoryerror",
            "heap exhausted",
            "memory pressure",
            "out of memory",
            "oom",
            "rss",
            "not responding",
            "unreachable",
        )
    )


def _evidence(primary: str, extra: str) -> list[str]:
    extra = extra.strip()
    if extra:
        return [primary, extra[:240]]
    return [primary]
