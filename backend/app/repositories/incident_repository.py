"""SQLite persistence for incidents."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from backend.app.db.database import Database
from backend.app.models.incident import IncidentStatus
from backend.app.models.schemas import (
    AnalysisResult,
    ApprovalRecord,
    HistoryEvent,
    IncidentPublic,
    ValidationResults,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _dt_to_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


class IncidentRepository:
    def __init__(self, database: Database) -> None:
        self.db = database

    def create(self, incident: IncidentPublic) -> IncidentPublic:
        payload = self._to_row(incident)
        with self.db.lock:
            conn = self.db.connect()
            try:
                conn.execute(
                    """
                    INSERT INTO incidents (
                        id, title, error_message, stack_trace, repository_path, status,
                        root_cause_analysis, proposed_patch, validation_results, approval,
                        history, created_at, updated_at
                    ) VALUES (
                        :id, :title, :error_message, :stack_trace, :repository_path, :status,
                        :root_cause_analysis, :proposed_patch, :validation_results, :approval,
                        :history, :created_at, :updated_at
                    )
                    """,
                    payload,
                )
                conn.commit()
            finally:
                conn.close()
        return incident

    def get(self, incident_id: str) -> IncidentPublic | None:
        with self.db.lock:
            conn = self.db.connect()
            try:
                row = conn.execute(
                    "SELECT * FROM incidents WHERE id = ?", (incident_id,)
                ).fetchone()
            finally:
                conn.close()
        return self._from_row(row) if row else None

    def list(self) -> list[IncidentPublic]:
        with self.db.lock:
            conn = self.db.connect()
            try:
                rows = conn.execute(
                    "SELECT * FROM incidents ORDER BY created_at DESC"
                ).fetchall()
            finally:
                conn.close()
        return [self._from_row(row) for row in rows]

    def save(self, incident: IncidentPublic) -> IncidentPublic:
        incident.updated_at = _utcnow()
        payload = self._to_row(incident)
        with self.db.lock:
            conn = self.db.connect()
            try:
                conn.execute(
                    """
                    UPDATE incidents SET
                        title = :title,
                        error_message = :error_message,
                        stack_trace = :stack_trace,
                        repository_path = :repository_path,
                        status = :status,
                        root_cause_analysis = :root_cause_analysis,
                        proposed_patch = :proposed_patch,
                        validation_results = :validation_results,
                        approval = :approval,
                        history = :history,
                        updated_at = :updated_at
                    WHERE id = :id
                    """,
                    payload,
                )
                conn.commit()
            finally:
                conn.close()
        return incident

    def _to_row(self, incident: IncidentPublic) -> dict[str, Any]:
        return {
            "id": incident.id,
            "title": incident.title,
            "error_message": incident.error_message,
            "stack_trace": incident.stack_trace,
            "repository_path": incident.repository_path,
            "status": incident.status.value,
            "root_cause_analysis": (
                incident.root_cause_analysis.model_dump_json()
                if incident.root_cause_analysis
                else None
            ),
            "proposed_patch": incident.proposed_patch,
            "validation_results": (
                incident.validation_results.model_dump_json()
                if incident.validation_results
                else None
            ),
            "approval": incident.approval.model_dump_json() if incident.approval else None,
            "history": json.dumps([event.model_dump(mode="json") for event in incident.history]),
            "created_at": _dt_to_iso(incident.created_at),
            "updated_at": _dt_to_iso(incident.updated_at),
        }

    def _from_row(self, row: Any) -> IncidentPublic:
        history_raw = json.loads(row["history"] or "[]")
        return IncidentPublic(
            id=row["id"],
            title=row["title"],
            error_message=row["error_message"],
            stack_trace=row["stack_trace"],
            repository_path=row["repository_path"],
            status=IncidentStatus(row["status"]),
            root_cause_analysis=(
                AnalysisResult.model_validate_json(row["root_cause_analysis"])
                if row["root_cause_analysis"]
                else None
            ),
            proposed_patch=row["proposed_patch"],
            validation_results=(
                ValidationResults.model_validate_json(row["validation_results"])
                if row["validation_results"]
                else None
            ),
            approval=(
                ApprovalRecord.model_validate_json(row["approval"]) if row["approval"] else None
            ),
            history=[HistoryEvent.model_validate(item) for item in history_raw],
            created_at=_parse_dt(row["created_at"]),
            updated_at=_parse_dt(row["updated_at"]),
        )
