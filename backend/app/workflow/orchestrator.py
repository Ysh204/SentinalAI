"""Incident workflow orchestrator.

States:
RECEIVED → ANALYZING → ANALYZED → PATCH_GENERATED → VALIDATING → VALIDATED → APPROVED
Failures use FAILED or VALIDATION_FAILED. Humans can REJECT.

This module is the seam where a later LangGraph graph can call the same services.
"""

from __future__ import annotations

import threading
from collections import defaultdict

from backend.app.core.exceptions import InvalidTransitionError, SentinelAIError
from backend.app.models.incident import (
    ANALYZE_FROM,
    APPROVE_FROM,
    GENERATE_PATCH_FROM,
    REJECT_FROM,
    VALIDATE_FROM,
    IncidentStatus,
)
from backend.app.models.schemas import ApproveRequest, IncidentPublic, RejectRequest
from backend.app.services.analyzer import Analyzer
from backend.app.services.approval_service import ApprovalService
from backend.app.services.incident_service import IncidentService
from backend.app.services.patcher import Patcher
from backend.app.services.validator import Validator


class Orchestrator:
    def __init__(
        self,
        incidents: IncidentService,
        analyzer: Analyzer,
        patcher: Patcher,
        validator: Validator,
        approvals: ApprovalService,
    ) -> None:
        self.incidents = incidents
        self.analyzer = analyzer
        self.patcher = patcher
        self.validator = validator
        self.approvals = approvals
        self._locks: dict[str, threading.Lock] = defaultdict(threading.Lock)

    def analyze(self, incident_id: str) -> IncidentPublic:
        with self._locks[incident_id]:
            incident = self.incidents.get(incident_id)
            self.incidents.require_not_busy(incident)
            if incident.status not in ANALYZE_FROM:
                raise InvalidTransitionError(
                    f"Cannot analyze from status {incident.status.value}."
                )
            incident = self.incidents.transition(
                incident, IncidentStatus.ANALYZING, "analyze_started"
            )
            try:
                analysis = self.analyzer.analyze(incident)
            except Exception:
                self.incidents.transition(
                    incident, IncidentStatus.FAILED, "analyze_failed", "Analyzer did not complete."
                )
                raise
            incident.root_cause_analysis = analysis
            return self.incidents.transition(
                incident,
                IncidentStatus.ANALYZED,
                "analyze_completed",
                "AI-generated hypothesis stored.",
            )

    def generate_patch(self, incident_id: str) -> IncidentPublic:
        with self._locks[incident_id]:
            incident = self.incidents.get(incident_id)
            self.incidents.require_not_busy(incident)
            if incident.status not in GENERATE_PATCH_FROM:
                raise InvalidTransitionError(
                    f"Cannot generate a patch from status {incident.status.value}."
                )
            if not incident.root_cause_analysis:
                raise InvalidTransitionError("Analyze the incident before generating a patch.")
            try:
                patch = self.patcher.generate(incident)
            except SentinelAIError:
                self.incidents.transition(
                    incident,
                    IncidentStatus.FAILED,
                    "patch_failed",
                    "No usable patch was stored.",
                )
                raise
            incident.proposed_patch = patch
            incident.validation_results = None
            return self.incidents.transition(
                incident,
                IncidentStatus.PATCH_GENERATED,
                "patch_generated",
                "Proposed unified diff stored. Original repository was not modified.",
            )

    def validate(self, incident_id: str) -> IncidentPublic:
        with self._locks[incident_id]:
            incident = self.incidents.get(incident_id)
            self.incidents.require_not_busy(incident)
            if incident.status not in VALIDATE_FROM:
                raise InvalidTransitionError(
                    f"Cannot validate from status {incident.status.value}."
                )
            if not incident.proposed_patch:
                raise InvalidTransitionError("A proposed patch is required before validation.")
            incident = self.incidents.transition(
                incident, IncidentStatus.VALIDATING, "validate_started"
            )
            results = self.validator.validate(incident)
            incident.validation_results = results
            if results.overall_passed:
                return self.incidents.transition(
                    incident,
                    IncidentStatus.VALIDATED,
                    "validate_passed",
                    "Workspace tests passed. This is not a correctness guarantee.",
                )
            return self.incidents.transition(
                incident,
                IncidentStatus.VALIDATION_FAILED,
                "validate_failed",
                "Validation did not pass. Approval is blocked.",
            )

    def approve(self, incident_id: str, request: ApproveRequest) -> IncidentPublic:
        with self._locks[incident_id]:
            incident = self.incidents.get(incident_id)
            self.incidents.require_not_busy(incident)
            if incident.status not in APPROVE_FROM:
                raise InvalidTransitionError(
                    f"Cannot approve from status {incident.status.value}."
                )
            record = self.approvals.approve(incident, actor=request.actor, note=request.note)
            incident.approval = record
            return self.incidents.transition(
                incident,
                IncidentStatus.APPROVED,
                "approved",
                "Human approved the patch. No merge, push, or deploy was performed.",
            )

    def reject(self, incident_id: str, request: RejectRequest) -> IncidentPublic:
        with self._locks[incident_id]:
            incident = self.incidents.get(incident_id)
            self.incidents.require_not_busy(incident)
            if incident.status not in REJECT_FROM:
                raise InvalidTransitionError(
                    f"Cannot reject from status {incident.status.value}."
                )
            record = self.approvals.reject(incident, actor=request.actor, reason=request.reason)
            incident.approval = record
            return self.incidents.transition(
                incident,
                IncidentStatus.REJECTED,
                "rejected",
                request.reason,
            )
