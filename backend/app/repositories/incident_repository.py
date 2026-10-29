"""SQLite persistence for incidents."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from backend.app.core.exceptions import NotFoundError, SentinelAIError
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
                        history, details, fingerprint, version, created_at, updated_at
                    ) VALUES (
                        :id, :title, :error_message, :stack_trace, :repository_path, :status,
                        :root_cause_analysis, :proposed_patch, :validation_results, :approval,
                        :history, :details, :fingerprint, :version, :created_at, :updated_at
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

    def list(self, limit: int | None = 100, offset: int = 0) -> list[IncidentPublic]:
        """Newest first. ``limit=None`` returns everything (use for aggregates, not for API pages)."""
        query = "SELECT * FROM incidents ORDER BY created_at DESC"
        params: tuple = ()
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params = (limit, offset)
        with self.db.lock:
            conn = self.db.connect()
            try:
                rows = conn.execute(query, params).fetchall()
            finally:
                conn.close()
        return [self._from_row(row) for row in rows]

    def list_by_status(self, statuses) -> list[IncidentPublic]:
        values = sorted({getattr(status, "value", status) for status in statuses})
        if not values:
            return []
        placeholders = ",".join("?" for _ in values)
        with self.db.lock:
            conn = self.db.connect()
            try:
                rows = conn.execute(
                    f"SELECT * FROM incidents WHERE status IN ({placeholders}) ORDER BY created_at DESC",
                    tuple(values),
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
                    "SELECT * FROM incidents WHERE fingerprint = ? ORDER BY created_at DESC",
                    (fingerprint,),
                ).fetchall()
            finally:
                conn.close()
        for row in rows:
            incident = self._from_row(row)
            if incident.status.value not in closed:
                return incident
        return None

    def save(self, incident: IncidentPublic) -> IncidentPublic:
        incident.updated_at = _utcnow()
        payload = self._to_row(incident)
        with self.db.lock:
            conn = self.db.connect()
            try:
                cursor = conn.execute(
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
                        fingerprint = :fingerprint,
                        updated_at = :updated_at,
                        version = version + 1
                    WHERE id = :id AND version = :version
                    """,
                    payload,
                )
                if cursor.rowcount == 0:
                    raise SentinelAIError(
                        "Incident was modified concurrently (version conflict).",
                        code="conflict",
                        status_code=409,
                    )
                conn.commit()
                incident.version += 1
            finally:
                conn.close()
        return incident

    def record_duplicate_alert(
        self,
        incident_id: str,
        new_logs: list[str] | None = None,
        event: HistoryEvent | None = None,
        error_message: str | None = None,
        stack_trace: str | None = None,
        captured_request: dict[str, Any] | None = None,
    ) -> IncidentPublic:
        """Atomically record a grouped duplicate alert without incrementing row version."""
        with self.db.lock:
            conn = self.db.connect()
            try:
                row = conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
                if not row:
                    raise NotFoundError(f"Incident {incident_id} was not found.")
                keys = row.keys() if hasattr(row, "keys") else []
                details = json.loads(row["details"] if "details" in keys else "{}")
                history = json.loads(row["history"] if "history" in keys else "[]")

                details["occurrence_count"] = int(details.get("occurrence_count") or 1) + 1
                if new_logs:
                    current_logs = details.get("logs") or []
                    details["logs"] = (current_logs + new_logs)[-80:]
                if captured_request:
                    details["captured_request"] = captured_request
                if event:
                    history.append(event.model_dump(mode="json"))
                    history = history[-50:]

                updated_at = _dt_to_iso(_utcnow())
                new_err = error_message if error_message is not None else row["error_message"]
                new_stack = stack_trace if stack_trace is not None else row["stack_trace"]

                conn.execute(
                    """
                    UPDATE incidents SET
                        details = ?,
                        history = ?,
                        error_message = ?,
                        stack_trace = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (json.dumps(details), json.dumps(history), new_err, new_stack, updated_at, incident_id),
                )
                conn.commit()
                updated_row = conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
                return self._from_row(updated_row)
            finally:
                conn.close()

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
            "fingerprint": incident.fingerprint,
            "version": incident.version,
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
        fp = row["fingerprint"] if "fingerprint" in keys and row["fingerprint"] else details.get("fingerprint")
        version = int(row["version"]) if "version" in keys and row["version"] is not None else 1
        return IncidentPublic(
            id=row["id"],
            title=row["title"],
            error_message=row["error_message"],
            stack_trace=row["stack_trace"],
            repository_path=row["repository_path"],
            status=IncidentStatus(row["status"]),
            source=details.get("source") or "manual",
            service=details.get("service"),
            fingerprint=fp,
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
            version=version,
            created_at=_parse_dt(row["created_at"]),
            updated_at=_parse_dt(row["updated_at"]),
        )
