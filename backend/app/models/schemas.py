"""Pydantic request and response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from backend.app.models.incident import IncidentStatus, RecommendedTrack, VerdictCategory


class IncidentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=240)
    error_message: str = Field(..., min_length=1)
    stack_trace: str = ""
    repository_path: str | None = None


class AlertCreate(BaseModel):
    source: str = "webhook"
    service: str = "checkout"
    title: str | None = None
    error_message: str = Field(..., min_length=1)
    stack_trace: str = ""
    endpoint: str | None = None
    status_code: int | None = None
    captured_request: dict[str, Any] | None = None
    logs: list[str] = Field(default_factory=list)
    fingerprint: str | None = None
    repository_path: str | None = "victim_app"
    occurred_at: str | None = None


class HistoryEvent(BaseModel):
    timestamp: datetime
    from_status: IncidentStatus | None
    to_status: IncidentStatus
    event: str
    detail: str = ""


class AnalysisResult(BaseModel):
    hypothesis: str
    suspected_file: str | None = None
    suspected_function: str | None = None
    confidence: str = "medium"
    recommended_next_steps: list[str] = Field(default_factory=list)
    disclaimer: str = (
        "AI-generated hypothesis, not verified fact. A human must review before any change."
    )
    provider: str
    source_files_considered: list[str] = Field(default_factory=list)


class Verdict(BaseModel):
    category: VerdictCategory
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)
    recommended_track: RecommendedTrack
    escalate_to_human: bool = False
    recommended_action: str | None = None
    provider: str = "mock"
    disclaimer: str = (
        "Triage verdict is a hypothesis. Low confidence must escalate instead of guessing."
    )


class ValidationCheck(BaseModel):
    name: str
    status: str
    detail: str = ""
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""


class ValidationResults(BaseModel):
    overall_passed: bool
    checks: list[ValidationCheck] = Field(default_factory=list)
    applied_files: list[str] = Field(default_factory=list)
    workspace: str | None = None
    disclaimer: str = (
        "A passing test run does not guarantee the fix is correct, complete, or safe."
    )


class ReplayResult(BaseModel):
    before_status: int | None = None
    after_status: int | None = None
    before_ok: bool = False
    after_ok: bool = False
    request_path: str = "/checkout"
    detail: str = ""
    sandbox: str | None = None


class MitigationRecord(BaseModel):
    action: str
    simulated: bool = True
    status: str = "proposed"
    executed_at: datetime | None = None
    actor: str | None = None
    error_rate_before: float | None = None
    error_rate_after: float | None = None
    recovered: bool | None = None
    detail: str = ""


class Postmortem(BaseModel):
    summary: str
    root_cause: str
    action_items: list[str] = Field(default_factory=list)
    provider: str = "mock"
    generated_at: datetime | None = None


class ApprovalRecord(BaseModel):
    decision: str
    reason: str | None = None
    decided_at: datetime
    actor: str = "human"


class RejectRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=2000)
    actor: str = "human"


class ApproveRequest(BaseModel):
    actor: str = "human"
    note: str | None = None


class BreakRequest(BaseModel):
    mode: str = Field(..., min_length=1)


class IncidentPublic(BaseModel):
    id: str
    title: str
    error_message: str
    stack_trace: str
    repository_path: str | None
    status: IncidentStatus
    source: str = "manual"
    service: str | None = None
    fingerprint: str | None = None
    occurrence_count: int = 1
    captured_request: dict[str, Any] | None = None
    logs: list[str] = Field(default_factory=list)
    context: dict[str, Any] | None = None
    verdict: Verdict | None = None
    root_cause_analysis: AnalysisResult | None = None
    proposed_patch: str | None = None
    validation_results: ValidationResults | None = None
    replay: ReplayResult | None = None
    mitigation: MitigationRecord | None = None
    postmortem: Postmortem | None = None
    approval: ApprovalRecord | None = None
    history: list[HistoryEvent] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class HealthResponse(BaseModel):
    status: str
    app: str
    team: str
    version: str
    ai_provider: str
    gemini_configured: bool
    database_ready: bool
    victim_app_url: str | None = None
    notes: str = "SentinelAI is a web service that watches other web services. Demo environment."


class MetricsResponse(BaseModel):
    incidents_total: int
    by_status: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    mean_time_to_resolution_seconds: float | None = None
    open_count: int = 0


class ErrorResponse(BaseModel):
    detail: str
    code: str | None = None
    extra: dict[str, Any] | None = None
