"""Incident workflow orchestrator."""

from __future__ import annotations

import threading
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from backend.app.core.exceptions import InvalidTransitionError, SentinelAIError
from backend.app.models.incident import (
    ANALYZE_FROM,
    APPROVE_FROM,
    GENERATE_PATCH_FROM,
    IN_PROGRESS_STATUSES,
    MITIGATE_PROPOSE_FROM,
    REJECT_FROM,
    REPLAY_FROM,
    TRIAGE_FROM,
    VALIDATE_FROM,
    IncidentStatus,
    RecommendedTrack,
)
from backend.app.models.schemas import ApproveRequest, IncidentPublic, RejectRequest
from backend.app.services.analyzer import Analyzer
from backend.app.services.approval_service import ApprovalService
from backend.app.services.incident_service import IncidentService
from backend.app.services.mitigation import MitigationService
from backend.app.services.patcher import Patcher
from backend.app.services.postmortem import PostmortemService
from backend.app.services.replay_service import ReplayService, as_check
from backend.app.services.triage import TriageEngine
from backend.app.services.validator import Validator


class Orchestrator:
    def __init__(
        self,
        incidents: IncidentService,
        analyzer: Analyzer,
        patcher: Patcher,
        validator: Validator,
        approvals: ApprovalService,
        triage: TriageEngine,
        mitigation: MitigationService,
        replay_service: ReplayService,
        postmortems: PostmortemService,
    ) -> None:
        self.incidents = incidents
        self.analyzer = analyzer
        self.patcher = patcher
        self.validator = validator
        self.approvals = approvals
        self.triage = triage
        self.mitigation = mitigation
        self.replay_service = replay_service
        self.postmortems = postmortems
        self._locks: dict[str, threading.Lock] = defaultdict(threading.Lock)

    def recover_stuck_incidents(self, max_age_seconds: float = 0.0) -> list[str]:
        """Fail incidents left in an in-progress status by a crash.

        Only incidents idle for longer than ``max_age_seconds`` are touched, and any incident whose
        lock is currently held by a live worker in this process is skipped, so a sweep never
        kills a healthy operation.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)
        recovered: list[str] = []
        for stale in self.incidents.list_by_status(IN_PROGRESS_STATUSES):
            if stale.updated_at > cutoff:
                continue
            lock = self._locks[stale.id]
            if not lock.acquire(blocking=False):
                continue  # a live worker owns it
            try:
                incident = self.incidents.get(stale.id)
                if incident.status not in IN_PROGRESS_STATUSES:
                    continue
                self.incidents.transition(
                    incident,
                    IncidentStatus.FAILED,
                    "stuck_recovery",
                    f"No progress for over {int(max_age_seconds)}s in {incident.status.value}; reset to FAILED.",
                )
                recovered.append(incident.id)
            finally:
                lock.release()
        return recovered

    def triage_incident(self, incident_id: str) -> IncidentPublic:
        with self._locks[incident_id]:
            incident = self.incidents.get(incident_id)
            self.incidents.require_not_busy(incident)
            if incident.status not in TRIAGE_FROM:
                raise InvalidTransitionError(
                    f"Cannot triage from status {incident.status.value}."
                )
            incident = self.incidents.transition(
                incident, IncidentStatus.TRIAGING, "triage_started"
            )
            try:
                verdict, context = self.triage.run(incident)
                incident.verdict = verdict
                incident.context = context
                next_status = IncidentStatus.TRIAGED
                detail = f"{verdict.category.value} ({verdict.confidence:.2f})"
                if verdict.recommended_track == RecommendedTrack.MITIGATION:
                    incident.mitigation = self.mitigation.propose(incident)
                    next_status = IncidentStatus.MITIGATION_PROPOSED
                    detail += f"; proposed {incident.mitigation.action}"
                elif verdict.escalate_to_human:
                    detail += "; escalated to human"
            except Exception as exc:
                self.incidents.transition(
                    incident,
                    IncidentStatus.FAILED,
                    "triage_failed",
                    f"Triage did not complete: {exc}",
                )
                raise
            return self.incidents.transition(
                incident, next_status, "triage_completed", detail
            )

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
            if not incident.root_cause_analysis and not (
                incident.verdict and incident.verdict.recommended_track == RecommendedTrack.CODE_FIX
            ):
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
            try:
                results = self.validator.validate(incident)
            except Exception as exc:
                self.incidents.transition(
                    incident,
                    IncidentStatus.VALIDATION_FAILED,
                    "validate_failed",
                    f"Validation failed with unexpected error: {exc}",
                )
                raise
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

    def replay(self, incident_id: str) -> IncidentPublic:
        with self._locks[incident_id]:
            incident = self.incidents.get(incident_id)
            self.incidents.require_not_busy(incident)
            if incident.status not in REPLAY_FROM:
                raise InvalidTransitionError(
                    f"Cannot replay from status {incident.status.value}."
                )
            incident = self.incidents.transition(
                incident, IncidentStatus.REPLAYING, "replay_started"
            )
            try:
                result = self.replay_service.replay(incident)
            except Exception as exc:
                self.incidents.transition(
                    incident,
                    IncidentStatus.VALIDATION_FAILED,
                    "replay_failed",
                    f"Replay failed with unexpected error: {exc}",
                )
                raise
            incident.replay = result
            if incident.validation_results:
                incident.validation_results.checks = [
                    c for c in incident.validation_results.checks if c.name != "request_replay"
                ]
                incident.validation_results.checks.append(as_check(result))
            if result.after_ok and not result.before_ok:
                return self.incidents.transition(
                    incident,
                    IncidentStatus.PATCH_VERIFIED,
                    "replay_passed",
                    "Captured request failed before the patch and succeeded after.",
                )
            return self.incidents.transition(
                incident,
                IncidentStatus.VALIDATION_FAILED,
                "replay_failed",
                result.detail,
            )

    def propose_mitigation(self, incident_id: str) -> IncidentPublic:
        with self._locks[incident_id]:
            incident = self.incidents.get(incident_id)
            self.incidents.require_not_busy(incident)
            if incident.status not in MITIGATE_PROPOSE_FROM:
                raise InvalidTransitionError(
                    f"Cannot propose mitigation from status {incident.status.value}."
                )
            incident.mitigation = self.mitigation.propose(incident)
            return self.incidents.transition(
                incident,
                IncidentStatus.MITIGATION_PROPOSED,
                "mitigation_proposed",
                f"Simulated action {incident.mitigation.action} waiting for human approval.",
            )

    def approve(self, incident_id: str, request: ApproveRequest) -> IncidentPublic:
        with self._locks[incident_id]:
            incident = self.incidents.get(incident_id)
            self.incidents.require_not_busy(incident)
            if incident.status not in APPROVE_FROM:
                raise InvalidTransitionError(
                    f"Cannot approve from status {incident.status.value}."
                )
            if incident.status == IncidentStatus.MITIGATION_PROPOSED:
                approval = self.approvals.approve(incident, actor=request.actor, note=request.note)
                incident.approval = approval
                incident = self.incidents.transition(
                    incident, IncidentStatus.MITIGATING, "mitigation_started", "Human approved.", actor=request.actor
                )
                try:
                    record = self.mitigation.execute(incident, actor=request.actor)
                except Exception as exc:
                    self.incidents.transition(
                        incident,
                        IncidentStatus.FAILED,
                        "mitigation_failed",
                        f"Mitigation failed with unexpected error: {exc}",
                        actor=request.actor,
                    )
                    raise
                incident.mitigation = record
                next_status = IncidentStatus.MITIGATED if record.recovered else IncidentStatus.FAILED
                return self.incidents.transition(
                    incident,
                    next_status,
                    "mitigation_executed",
                    record.detail,
                    actor=request.actor,
                )
            record = self.approvals.approve(incident, actor=request.actor, note=request.note)
            incident.approval = record
            return self.incidents.transition(
                incident,
                IncidentStatus.APPROVED,
                "approved",
                "Human approved the patch. No merge, push, or deploy was performed.",
                actor=request.actor,
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
                actor=request.actor,
            )

    def postmortem(self, incident_id: str) -> IncidentPublic:
        with self._locks[incident_id]:
            incident = self.incidents.get(incident_id)
            report = self.postmortems.generate(incident)
            incident.postmortem = report
            stored = self.incidents.save(incident)
            if incident.status in {IncidentStatus.MITIGATED, IncidentStatus.APPROVED}:
                return self.incidents.transition(
                    stored, IncidentStatus.RESOLVED, "postmortem_generated", "Report stored."
                )
            return stored
