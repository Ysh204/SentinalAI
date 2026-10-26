"""Human approval and rejection. Does not merge, push, or deploy."""

from __future__ import annotations

from datetime import datetime, timezone

from backend.app.core.exceptions import SentinelAIError
from backend.app.models.incident import IncidentStatus
from backend.app.models.schemas import ApprovalRecord, IncidentPublic


class ApprovalService:
    def approve(self, incident: IncidentPublic, actor: str, note: str | None = None) -> ApprovalRecord:
        if incident.status == IncidentStatus.MITIGATION_PROPOSED:
            return ApprovalRecord(
                decision="approved",
                reason=note or "Human approved simulated mitigation.",
                decided_at=datetime.now(timezone.utc),
                actor=actor or "human",
            )
        if not incident.proposed_patch:
            raise SentinelAIError(
                "Approval requires a proposed patch.",
                code="missing_patch",
                status_code=409,
            )
        if incident.status not in {IncidentStatus.VALIDATED, IncidentStatus.PATCH_VERIFIED}:
            raise SentinelAIError(
                "Approval is allowed only after validation has completed successfully.",
                code="approval_blocked",
                status_code=409,
            )
        if not incident.validation_results or not incident.validation_results.overall_passed:
            raise SentinelAIError(
                "Approval is blocked because validation did not pass.",
                code="validation_failed",
                status_code=409,
            )
        return ApprovalRecord(
            decision="approved",
            reason=note,
            decided_at=datetime.now(timezone.utc),
            actor=actor or "human",
        )

    def reject(self, incident: IncidentPublic, actor: str, reason: str) -> ApprovalRecord:
        if not reason.strip():
            raise SentinelAIError("A rejection reason is required.", code="missing_reason", status_code=400)
        return ApprovalRecord(
            decision="rejected",
            reason=reason.strip(),
            decided_at=datetime.now(timezone.utc),
            actor=actor or "human",
        )
