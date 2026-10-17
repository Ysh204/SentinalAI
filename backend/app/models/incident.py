"""Incident domain types and allowed workflow transitions."""

from __future__ import annotations

from enum import StrEnum


class IncidentStatus(StrEnum):
    RECEIVED = "RECEIVED"
    ANALYZING = "ANALYZING"
    ANALYZED = "ANALYZED"
    PATCH_GENERATED = "PATCH_GENERATED"
    VALIDATING = "VALIDATING"
    VALIDATED = "VALIDATED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


TERMINAL_STATUSES = {IncidentStatus.APPROVED, IncidentStatus.REJECTED}

ANALYZE_FROM = {IncidentStatus.RECEIVED, IncidentStatus.FAILED}
GENERATE_PATCH_FROM = {
    IncidentStatus.ANALYZED,
    IncidentStatus.PATCH_GENERATED,
    IncidentStatus.VALIDATION_FAILED,
    IncidentStatus.FAILED,
}
VALIDATE_FROM = {
    IncidentStatus.PATCH_GENERATED,
    IncidentStatus.VALIDATION_FAILED,
    IncidentStatus.VALIDATED,
}
APPROVE_FROM = {IncidentStatus.VALIDATED}
REJECT_FROM = {
    IncidentStatus.ANALYZED,
    IncidentStatus.PATCH_GENERATED,
    IncidentStatus.VALIDATED,
    IncidentStatus.VALIDATION_FAILED,
    IncidentStatus.FAILED,
}

IN_PROGRESS_STATUSES = {IncidentStatus.ANALYZING, IncidentStatus.VALIDATING}
