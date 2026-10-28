"""Deterministic triage from observable logs and telemetry — never injector labels."""

from __future__ import annotations

import re
from typing import Any

from backend.app.models.incident import RecommendedTrack, VerdictCategory
from backend.app.models.schemas import IncidentPublic, Verdict

LOW_CONFIDENCE = 0.55


def observable_victim(context: dict[str, Any]) -> dict[str, Any]:
    if not context:
        return {"recent_logs": []}
    victim_data = context.get("victim")
    victim = dict(victim_data if isinstance(victim_data, dict) else context)
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

    is_bug, bug_conf = _looks_like_code_bug(text, incident)
    if is_bug:
        return Verdict(
            category=VerdictCategory.CODE_BUG,
            confidence=bug_conf,
            evidence=_evidence(
                "Application stack raised TypeError/AttributeError in shop code",
                incident.stack_trace or incident.error_message,
            ),
            recommended_track=RecommendedTrack.CODE_FIX,
            escalate_to_human=False,
            recommended_action="patch",
            provider=provider,
        )

    is_key, key_conf = _looks_like_expired_key(text, status, key_status, payments)
    if is_key:
        return Verdict(
            category=VerdictCategory.CONFIG,
            confidence=key_conf,
            evidence=_evidence(
                "Payments rejected the configured credential (401/expired/invalid key)",
                f"key_status={key_status or 'unknown'}",
            ),
            recommended_track=RecommendedTrack.MITIGATION,
            escalate_to_human=False,
            recommended_action="restore_config",
            provider=provider,
        )

    is_dep, dep_conf = _looks_like_dependency_outage(text, status, payments)
    if is_dep:
        return Verdict(
            category=VerdictCategory.DEPENDENCY_OUTAGE,
            confidence=dep_conf,
            evidence=_evidence(
                "Checkout failed because the payments dependency is down or timing out",
                f"dependency_health.payments={payments or 'unknown'}",
            ),
            recommended_track=RecommendedTrack.MITIGATION,
            escalate_to_human=False,
            recommended_action="fallback",
            provider=provider,
        )

    is_deploy, deploy_conf = _looks_like_bad_deploy(text, victim)
    if is_deploy:
        return Verdict(
            category=VerdictCategory.BAD_DEPLOY,
            confidence=deploy_conf,
            evidence=_evidence(
                "Failure tracks a recent checkout deploy whose diff changes request handling",
                str(victim.get("last_deploy_diff") or incident.error_message),
            ),
            recommended_track=RecommendedTrack.MITIGATION,
            escalate_to_human=False,
            recommended_action="rollback",
            provider=provider,
        )

    is_res, res_conf = _looks_like_resource(text, memory_bytes, victim)
    if is_res:
        return Verdict(
            category=VerdictCategory.RESOURCE,
            confidence=res_conf,
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


def _looks_like_code_bug(text: str, incident: IncidentPublic) -> tuple[bool, float]:
    stack = (incident.stack_trace or "").lower()
    error = (incident.error_message or "").lower()
    in_app_tokens = ("shop.py", "_line_total", "victim_app", "buggy_app")
    in_app = any(token in stack or token in text for token in in_app_tokens)
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
    is_bug = type_error and (in_app or "traceback" in stack or 'file "' in stack or "_line_total" in text)
    if not is_bug:
        return False, 0.0
    confidence = 0.88
    if in_app and ("traceback" in stack or "_line_total" in text):
        confidence = 0.92
    elif not in_app:
        confidence = 0.65
    return True, confidence


def _looks_like_expired_key(text: str, status: object, key_status: str, payments: str) -> tuple[bool, float]:
    if key_status in {"expired", "invalid"} or payments == "auth_failed":
        return True, 0.90
    try:
        code = int(status) if status is not None else None
    except (TypeError, ValueError):
        code = None

    has_auth_code = code == 401 or bool(re.search(r"\b401\b", text))
    has_auth_kw = any(
        kw in text
        for kw in (
            "unauthorized",
            "invalid api key",
            "api key expired",
            "expired credential",
            "token expired",
            "key rotation",
        )
    )
    if has_auth_code and ("deadlock" in text or "lock wait" in text):
        return False, 0.0

    if has_auth_code and has_auth_kw:
        return True, 0.88
    if has_auth_kw or (has_auth_code and "order ord-" not in text):
        return True, 0.80
    return False, 0.0


def _looks_like_dependency_outage(text: str, status: object, payments: str) -> tuple[bool, float]:
    if payments in {"down", "unavailable"}:
        return True, 0.90
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
    match = dependency and (
        code in {502, 503, 504}
        or "503" in text
        or "timeout" in text
        or "unavailable" in text
        or payments == "down"
    )
    if match:
        confidence = 0.88 if payments == "down" or code in {502, 503} else 0.82
        return True, confidence
    return False, 0.0


def _looks_like_bad_deploy(text: str, victim: dict[str, Any]) -> tuple[bool, float]:
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
    match = bool(deploy_signal and (runtime or "500" in text or "error rate" in text))
    if match:
        confidence = 0.90 if diff and runtime else 0.85
        return True, confidence
    return False, 0.0


def _looks_like_resource(text: str, memory_bytes: int, victim: dict[str, Any]) -> tuple[bool, float]:
    if memory_bytes > 2_000_000:
        return True, 0.92
    if victim.get("healthy") is False:
        return True, 0.85
    has_res_signal = bool(
        re.search(
            r"\b(oom|rss|memoryerror|heap exhausted|memory pressure|out of memory)\b",
            text,
        )
    ) or any(phrase in text for phrase in ("not responding", "unreachable"))
    if has_res_signal:
        return True, 0.85
    return False, 0.0


def _evidence(primary: str, extra: str) -> list[str]:
    extra = extra.strip()
    if extra:
        return [primary, extra[:240]]
    return [primary]
