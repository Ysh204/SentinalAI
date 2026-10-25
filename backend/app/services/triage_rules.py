"""Deterministic triage for the five demo failures. Used offline and as a demo backup."""

from __future__ import annotations

from typing import Any

from backend.app.models.incident import RecommendedTrack, VerdictCategory
from backend.app.models.schemas import IncidentPublic, Verdict

LOW_CONFIDENCE = 0.55


def _blob(incident: IncidentPublic, context: dict[str, Any]) -> str:
    victim = context.get("victim") or {}
    parts = [
        incident.title,
        incident.error_message,
        incident.stack_trace,
        " ".join(incident.logs[-20:]),
        str(victim.get("failure_mode") or ""),
        str(victim.get("last_deploy_diff") or ""),
        str((victim.get("config") or {}).get("payments_api_key_status") or ""),
        str((victim.get("dependency_health") or {}).get("payments") or ""),
        str(context.get("collector_error") or ""),
    ]
    return " ".join(parts).lower()


def classify(incident: IncidentPublic, context: dict[str, Any], provider: str) -> Verdict:
    text = _blob(incident, context)
    victim = context.get("victim") or {}
    mode = str(victim.get("failure_mode") or "")

    if mode == "code_bug" or "nonetype" in text or "not subscriptable" in text or "_line_total" in text:
        return Verdict(
            category=VerdictCategory.CODE_BUG,
            confidence=0.93,
            evidence=[
                "Checkout raised TypeError on a missing cart line",
                "Stack points at _line_total in shop.py",
            ],
            recommended_track=RecommendedTrack.CODE_FIX,
            escalate_to_human=False,
            recommended_action="patch",
            provider=provider,
        )
    if mode == "expired_key" or "api key expired" in text or "expired-key" in text:
        return Verdict(
            category=VerdictCategory.CONFIG,
            confidence=0.91,
            evidence=[
                "Payments API rejected the configured key",
                "No code change required to restore service",
            ],
            recommended_track=RecommendedTrack.MITIGATION,
            escalate_to_human=False,
            recommended_action="restore_config",
            provider=provider,
        )
    if (
        mode == "payments_outage"
        or "payments api unavailable" in text
        or "503" in text and "payment" in text
    ):
        return Verdict(
            category=VerdictCategory.DEPENDENCY_OUTAGE,
            confidence=0.86,
            evidence=[
                "Checkout received 503 from the payments dependency",
                victim.get("last_deploy_diff")
                and "last deploy: " + str(victim.get("last_deploy_diff"))
                or "no recent code deploy explaining the spike",
            ],
            recommended_track=RecommendedTrack.MITIGATION,
            escalate_to_human=False,
            recommended_action="fallback",
            provider=provider,
        )
    if mode == "bad_deploy" or "bad-2.0.0" in text or "after deploy" in text:
        return Verdict(
            category=VerdictCategory.BAD_DEPLOY,
            confidence=0.9,
            evidence=[
                "Error rate jumped immediately after deploy bad-2.0.0",
                "Handler raises RuntimeError on every paid order",
            ],
            recommended_track=RecommendedTrack.MITIGATION,
            escalate_to_human=False,
            recommended_action="rollback",
            provider=provider,
        )
    if mode == "memory_leak" or "memoryerror" in text or "heap exhausted" in text or "memory pressure" in text:
        return Verdict(
            category=VerdictCategory.RESOURCE,
            confidence=0.88,
            evidence=[
                "Memory sink grows on each checkout",
                "Health check reports memory pressure",
            ],
            recommended_track=RecommendedTrack.MITIGATION,
            escalate_to_human=False,
            recommended_action="restart",
            provider=provider,
        )
    if "unreachable" in text or "not responding" in text or mode == "crash":
        return Verdict(
            category=VerdictCategory.RESOURCE,
            confidence=0.8,
            evidence=["Health checks to /health failed repeatedly"],
            recommended_track=RecommendedTrack.MITIGATION,
            escalate_to_human=False,
            recommended_action="restart",
            provider=provider,
        )

    return Verdict(
        category=VerdictCategory.UNKNOWN,
        confidence=0.2,
        evidence=["Not enough signal to classify this failure"],
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
