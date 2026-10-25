"""SQLite persistence for incidents."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from backend.app.db.database import Database
from backend.app.models.incident import TERMINAL_STATUSES, IncidentStatus
from backend.app.models.schemas import (
    AnalysisResult,
    ApprovalRecord,
    HistoryEvent,
    IncidentPublic,
    MitigationRecord,
    Postmortem,
    ReplayResult,
    ValidationResults,
    Verdict,
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
                        history, details, created_at, updated_at
                    ) VALUES (
                        :id, :title, :error_message, :stack_trace, :repository_path, :status,
                        :root_cause_analysis, :proposed_patch, :validation_results, :approval,
                        :history, :details, :created_at, :updated_at
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

    def find_open_by_fingerprint(self, fingerprint: str) -> IncidentPublic | None:
        closed = {status.value for status in TERMINAL_STATUSES} | {
            IncidentStatus.MITIGATED.value,
            IncidentStatus.PATCH_VERIFIED.value,
        }
        with self.db.lock:
            conn = self.db.connect()
            try:
                rows = conn.execute(
                    "SELECT * FROM incidents ORDER BY created_at DESC"
                ).fetchall()
            finally:
                conn.close()
        for row in rows:
            incident = self._from_row(row)
            if incident.fingerprint == fingerprint and incident.status.value not in closed:
                return incident
        return None

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
                        details = :details,
                        updated_at = :updated_at
                    WHERE id = :id
                    """,
                    payload,
                )
                conn.commit()
            finally:
                conn.close()
        return incident

    def add_audit(self, incident_id: str | None, actor: str, action: str, detail: str = "") -> None:
        with self.db.lock:
            conn = self.db.connect()
            try:
                conn.execute(
                    """
                    INSERT INTO audit_log (timestamp, incident_id, actor, action, detail)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (_dt_to_iso(_utcnow()), incident_id, actor, action, detail),
                )
                conn.commit()
            finally:
                conn.close()

    def list_audit(self, incident_id: str | None = None) -> list[dict[str, Any]]:
        with self.db.lock:
            conn = self.db.connect()
            try:
                if incident_id:
                    rows = conn.execute(
                        "SELECT * FROM audit_log WHERE incident_id = ? ORDER BY id ASC",
                        (incident_id,),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM audit_log ORDER BY id DESC LIMIT 200"
                    ).fetchall()
            finally:
                conn.close()
        return [dict(row) for row in rows]

    def _to_row(self, incident: IncidentPublic) -> dict[str, Any]:
        details = {
            "source": incident.source,
            "service": incident.service,
            "fingerprint": incident.fingerprint,
            "occurrence_count": incident.occurrence_count,
            "captured_request": incident.captured_request,
            "logs": incident.logs,
            "context": incident.context,
            "verdict": incident.verdict.model_dump(mode="json") if incident.verdict else None,
            "replay": incident.replay.model_dump(mode="json") if incident.replay else None,
            "mitigation": incident.mitigation.model_dump(mode="json") if incident.mitigation else None,
            "postmortem": incident.postmortem.model_dump(mode="json") if incident.postmortem else None,
        }
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
            "details": json.dumps(details),
            "created_at": _dt_to_iso(incident.created_at),
            "updated_at": _dt_to_iso(incident.updated_at),
        }

    def _from_row(self, row: Any) -> IncidentPublic:
        history_raw = json.loads(row["history"] or "[]")
        keys = row.keys() if hasattr(row, "keys") else []
        details_raw = row["details"] if "details" in keys else "{}"
        details = json.loads(details_raw or "{}")
        verdict = details.get("verdict")
        replay = details.get("replay")
        mitigation = details.get("mitigation")
        postmortem = details.get("postmortem")
        return IncidentPublic(
            id=row["id"],
            title=row["title"],
            error_message=row["error_message"],
            stack_trace=row["stack_trace"],
            repository_path=row["repository_path"],
            status=IncidentStatus(row["status"]),
            source=details.get("source") or "manual",
            service=details.get("service"),
            fingerprint=details.get("fingerprint"),
            occurrence_count=int(details.get("occurrence_count") or 1),
            captured_request=details.get("captured_request"),
            logs=details.get("logs") or [],
            context=details.get("context"),
            verdict=Verdict.model_validate(verdict) if verdict else None,
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
            replay=ReplayResult.model_validate(replay) if replay else None,
            mitigation=MitigationRecord.model_validate(mitigation) if mitigation else None,
            postmortem=Postmortem.model_validate(postmortem) if postmortem else None,
            approval=(
                ApprovalRecord.model_validate_json(row["approval"]) if row["approval"] else None
            ),
            history=[HistoryEvent.model_validate(item) for item in history_raw],
            created_at=_parse_dt(row["created_at"]),
            updated_at=_parse_dt(row["updated_at"]),
        )
