"""Incident create/read helpers."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from backend.app.core.config import Settings
from backend.app.core.exceptions import NotFoundError, SentinelAIError
from backend.app.models.incident import IncidentStatus
from backend.app.models.schemas import HistoryEvent, IncidentCreate, IncidentPublic
from backend.app.repositories.incident_repository import IncidentRepository
from backend.app.services.source_context import resolve_repository_path


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


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
        return self.repository.create(incident)

    def get(self, incident_id: str) -> IncidentPublic:
        incident = self.repository.get(incident_id)
        if not incident:
            raise NotFoundError(f"Incident {incident_id} was not found.")
        return incident

    def list(self) -> list[IncidentPublic]:
        return self.repository.list()

    def transition(
        self,
        incident: IncidentPublic,
        new_status: IncidentStatus,
        event: str,
        detail: str = "",
    ) -> IncidentPublic:
        previous = incident.status
        if previous == new_status:
            return incident
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
        return self.repository.save(incident)

    def require_not_busy(self, incident: IncidentPublic) -> None:
        if incident.status in {IncidentStatus.ANALYZING, IncidentStatus.VALIDATING}:
            raise SentinelAIError(
                "This incident already has an in-progress operation.",
                code="in_progress",
                status_code=409,
            )
        if incident.status in {IncidentStatus.APPROVED, IncidentStatus.REJECTED}:
            raise SentinelAIError(
                f"Incident is already {incident.status.value} and cannot be changed.",
                code="terminal_state",
                status_code=409,
            )
