"""Pydantic request and response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from backend.app.models.incident import IncidentStatus


class IncidentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=240)
    error_message: str = Field(..., min_length=1)
    stack_trace: str = ""
    repository_path: str | None = None


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


class IncidentPublic(BaseModel):
    id: str
    title: str
    error_message: str
    stack_trace: str
    repository_path: str | None
    status: IncidentStatus
    root_cause_analysis: AnalysisResult | None = None
    proposed_patch: str | None = None
    validation_results: ValidationResults | None = None
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


class ErrorResponse(BaseModel):
    detail: str
    code: str | None = None
    extra: dict[str, Any] | None = None
