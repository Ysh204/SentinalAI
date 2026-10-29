"""Incident create/read helpers."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from backend.app.core.config import Settings
from backend.app.core.exceptions import NotFoundError, SentinelAIError
from backend.app.models.incident import IN_PROGRESS_STATUSES, TERMINAL_STATUSES, IncidentStatus
from backend.app.models.schemas import AlertCreate, HistoryEvent, IncidentCreate, IncidentPublic
from backend.app.repositories.incident_repository import IncidentRepository
from backend.app.services.events import hub
from backend.app.services.redact import redact_payload
from backend.app.services.source_context import resolve_repository_path

SERVICE_REPO_MAP = {
    "checkout": "victim_app",
    "sample": "sample_app",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def fingerprint_for(alert: AlertCreate) -> str:
    if alert.fingerprint:
        return alert.fingerprint
    raw = "|".join(
        [
            alert.service,
            alert.endpoint or "",
            (alert.error_message or "")[:160],
            (alert.stack_trace or "").splitlines()[-1] if alert.stack_trace else "",
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class IncidentService:
    def __init__(self, repository: IncidentRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    def create(self, payload: IncidentCreate) -> IncidentPublic:
        repo_path = payload.repository_path or "sample_app"
        resolve_repository_path(repo_path, self.settings)
        now = _utcnow()
        incident = IncidentPublic(
            id=str(uuid.uuid4()),
            title=payload.title.strip(),
            error_message=payload.error_message.strip(),
            stack_trace=payload.stack_trace or "",
            repository_path=repo_path,
            status=IncidentStatus.RECEIVED,
            source="manual",
            history=[
                HistoryEvent(
                    timestamp=now,
                    from_status=None,
                    to_status=IncidentStatus.RECEIVED,
                    event="created",
                    detail="Incident ingested.",
                )
            ],
            created_at=now,
            updated_at=now,
        )
        stored = self.repository.create(incident)
        self._notify(stored, "created")
        return stored

    def ingest_alert(self, alert: AlertCreate) -> IncidentPublic:
        allowed = getattr(self.settings, "allowed_repositories", ("sample_app", "victim_app"))
        if alert.repository_path and alert.repository_path in allowed:
            repo_path = alert.repository_path
        else:
            repo_path = SERVICE_REPO_MAP.get(alert.service, "victim_app")
        resolve_repository_path(repo_path, self.settings)
        fp = fingerprint_for(alert)
        existing = self.repository.find_open_by_fingerprint(fp)
        captured_raw = dict(alert.captured_request or {})
        if alert.status_code is not None:
            captured_raw.setdefault("status_code", alert.status_code)
        if alert.endpoint:
            captured_raw.setdefault("path", alert.endpoint)
        captured = redact_payload(captured_raw) if captured_raw else None
        if existing:
            existing.occurrence_count += 1
            existing.error_message = alert.error_message
            existing.stack_trace = alert.stack_trace or existing.stack_trace
            if captured:
                existing.captured_request = captured
            if alert.logs:
                existing.logs = (existing.logs + alert.logs)[-80:]
            existing.history.append(
                HistoryEvent(
                    timestamp=_utcnow(),
                    from_status=existing.status,
                    to_status=existing.status,
                    event="duplicate_alert",
                    detail=f"Grouped alert #{existing.occurrence_count} with fingerprint {fp}.",
                )
            )
            stored = self.repository.save(existing)
            self.repository.add_audit(stored.id, alert.source, "duplicate_alert", fp)
            self._notify(stored, "updated")
            return stored

        now = _utcnow()
        title = (alert.title or f"{alert.service} alert: {alert.error_message[:80]}").strip()
        incident = IncidentPublic(
            id=str(uuid.uuid4()),
            title=title[:240],
            error_message=alert.error_message.strip(),
            stack_trace=alert.stack_trace or "",
            repository_path=repo_path,
            status=IncidentStatus.RECEIVED,
            source=alert.source,
            service=alert.service,
            fingerprint=fp,
            captured_request=captured,
            logs=list(alert.logs or []),
            history=[
                HistoryEvent(
                    timestamp=now,
                    from_status=None,
                    to_status=IncidentStatus.RECEIVED,
                    event="alert_ingested",
                    detail=f"Alert from {alert.source} ({alert.endpoint or 'n/a'}).",
                )
            ],
            created_at=now,
            updated_at=now,
        )
        stored = self.repository.create(incident)
        self.repository.add_audit(stored.id, alert.source, "alert_ingested", title)
        self._notify(stored, "created")
        return stored

    def get(self, incident_id: str) -> IncidentPublic:
        incident = self.repository.get(incident_id)
        if not incident:
            raise NotFoundError(f"Incident {incident_id} was not found.")
        return incident

    def list(self, limit: int | None = 100, offset: int = 0) -> list[IncidentPublic]:
        return self.repository.list(limit=limit, offset=offset)

    def list_all(self) -> list[IncidentPublic]:
        """Unpaginated. Aggregates (metrics) must use this so they do not silently truncate at one page."""
        return self.repository.list(limit=None)

    def list_by_status(self, statuses) -> list[IncidentPublic]:
        return self.repository.list_by_status(statuses)

    def save(self, incident: IncidentPublic) -> IncidentPublic:
        stored = self.repository.save(incident)
        self._notify(stored, "updated")
        return stored

    def transition(
        self,
        incident: IncidentPublic,
        new_status: IncidentStatus,
        event: str,
        detail: str = "",
    ) -> IncidentPublic:
        previous = incident.status
        incident.history.append(
            HistoryEvent(
                timestamp=_utcnow(),
                from_status=previous,
                to_status=new_status,
                event=event,
                detail=detail,
            )
        )
        incident.status = new_status
        stored = self.repository.save(incident)
        self.repository.add_audit(stored.id, "system", event, detail)
        self._notify(stored, event)
        return stored

    def require_not_busy(self, incident: IncidentPublic) -> None:
        if incident.status in IN_PROGRESS_STATUSES:
            raise SentinelAIError(
                "This incident already has an in-progress operation.",
                code="in_progress",
                status_code=409,
            )
        if incident.status in TERMINAL_STATUSES:
            raise SentinelAIError(
                f"Incident is already {incident.status.value} and cannot be changed.",
                code="terminal_state",
                status_code=409,
            )

    def _notify(self, incident: IncidentPublic, event: str) -> None:
        hub.publish_sync(
            {
                "event": event,
                "id": incident.id,
                "status": incident.status.value,
                "title": incident.title,
            }
        )
