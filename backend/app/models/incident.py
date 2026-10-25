"""Incident domain types and allowed workflow transitions."""

from __future__ import annotations

from enum import StrEnum


class IncidentStatus(StrEnum):
    RECEIVED = "RECEIVED"
    TRIAGING = "TRIAGING"
    TRIAGED = "TRIAGED"
    ANALYZING = "ANALYZING"
    ANALYZED = "ANALYZED"
    PATCH_GENERATED = "PATCH_GENERATED"
    VALIDATING = "VALIDATING"
    VALIDATED = "VALIDATED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    REPLAYING = "REPLAYING"
    PATCH_VERIFIED = "PATCH_VERIFIED"
    MITIGATION_PROPOSED = "MITIGATION_PROPOSED"
    MITIGATING = "MITIGATING"
    MITIGATED = "MITIGATED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    RESOLVED = "RESOLVED"


class VerdictCategory(StrEnum):
    CODE_BUG = "code_bug"
    CONFIG = "config"
    DEPENDENCY_OUTAGE = "dependency_outage"
    BAD_DEPLOY = "bad_deploy"
    RESOURCE = "resource"
    UNKNOWN = "unknown"


class RecommendedTrack(StrEnum):
    CODE_FIX = "code_fix"
    MITIGATION = "mitigation"
    ESCALATE = "escalate"


TERMINAL_STATUSES = {
    IncidentStatus.APPROVED,
    IncidentStatus.REJECTED,
    IncidentStatus.RESOLVED,
}

ANALYZE_FROM = {
    IncidentStatus.RECEIVED,
    IncidentStatus.FAILED,
    IncidentStatus.TRIAGED,
    IncidentStatus.MITIGATION_PROPOSED,
}
GENERATE_PATCH_FROM = {
    IncidentStatus.ANALYZED,
    IncidentStatus.TRIAGED,
    IncidentStatus.PATCH_GENERATED,
    IncidentStatus.VALIDATION_FAILED,
    IncidentStatus.FAILED,
}
VALIDATE_FROM = {
    IncidentStatus.PATCH_GENERATED,
    IncidentStatus.VALIDATION_FAILED,
    IncidentStatus.VALIDATED,
}
REPLAY_FROM = {
    IncidentStatus.VALIDATED,
    IncidentStatus.PATCH_GENERATED,
    IncidentStatus.PATCH_VERIFIED,
}
TRIAGE_FROM = {
    IncidentStatus.RECEIVED,
    IncidentStatus.FAILED,
    IncidentStatus.TRIAGED,
}
MITIGATE_PROPOSE_FROM = {
    IncidentStatus.TRIAGED,
    IncidentStatus.ANALYZED,
    IncidentStatus.MITIGATION_PROPOSED,
}
APPROVE_FROM = {
    IncidentStatus.VALIDATED,
    IncidentStatus.PATCH_VERIFIED,
    IncidentStatus.MITIGATION_PROPOSED,
}
REJECT_FROM = {
    IncidentStatus.ANALYZED,
    IncidentStatus.TRIAGED,
    IncidentStatus.PATCH_GENERATED,
    IncidentStatus.VALIDATED,
    IncidentStatus.VALIDATION_FAILED,
    IncidentStatus.PATCH_VERIFIED,
    IncidentStatus.MITIGATION_PROPOSED,
    IncidentStatus.FAILED,
}

IN_PROGRESS_STATUSES = {
    IncidentStatus.ANALYZING,
    IncidentStatus.VALIDATING,
    IncidentStatus.TRIAGING,
    IncidentStatus.MITIGATING,
    IncidentStatus.REPLAYING,
}
