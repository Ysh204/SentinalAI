from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status

from backend.app.api.deps import get_current_actor
from backend.app.core.exceptions import SentinelAIError
from backend.app.models.schemas import IncidentCreate, IncidentPublic
from backend.app.services.source_context import resolve_repository_path

router = APIRouter(
    prefix="/api/incidents",
    tags=["incidents"],
    dependencies=[Depends(get_current_actor)],
)


@router.post("", response_model=IncidentPublic, status_code=status.HTTP_201_CREATED)
def create_incident(payload: IncidentCreate, request: Request) -> IncidentPublic:
    return request.app.state.container.incidents.create(payload)


@router.get("", response_model=list[IncidentPublic])
def list_incidents(
    request: Request,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[IncidentPublic]:
    return request.app.state.container.incidents.repository.list(limit=limit, offset=offset)


@router.get("/audit")
def list_audit(
    request: Request,
    incident_id: str | None = Query(None),
) -> list[dict[str, Any]]:
    return request.app.state.container.incidents.repository.list_audit(incident_id=incident_id)


@router.get("/{incident_id}", response_model=IncidentPublic)
def get_incident(incident_id: str, request: Request) -> IncidentPublic:
    return request.app.state.container.incidents.get(incident_id)


@router.get("/{incident_id}/audit")
def get_incident_audit(
    incident_id: str,
    request: Request,
) -> list[dict[str, Any]]:
    return request.app.state.container.incidents.repository.list_audit(incident_id=incident_id)


@router.get("/{incident_id}/source-file")
def get_source_file(
    incident_id: str,
    path: str = Query(..., min_length=1, max_length=200),
    request: Request = None,
) -> dict[str, Any]:
    incident = request.app.state.container.incidents.get(incident_id)
    repo = resolve_repository_path(incident.repository_path, request.app.state.container.settings)
    clean_path = path.replace("\\", "/").strip().lstrip("/")
    target = (repo / clean_path).resolve()
    if not target.is_relative_to(repo):
        raise SentinelAIError("File path must stay inside the repository.", code="unsafe_path", status_code=400)
    if not target.exists() or not target.is_file():
        raise SentinelAIError(f"File not found: {path}", code="file_not_found", status_code=404)
    if target.stat().st_size > 60_000:
        raise SentinelAIError("File is too large to display.", code="file_too_large", status_code=400)
    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = target.read_text(encoding="latin-1", errors="replace")
    return {
        "path": clean_path,
        "content": content,
        "size_bytes": len(content.encode("utf-8")),
        "line_count": len(content.splitlines()),
    }


@router.post("/{incident_id}/analyze", response_model=IncidentPublic)
def analyze_incident(incident_id: str, request: Request) -> IncidentPublic:
    return request.app.state.container.orchestrator.analyze(incident_id)


@router.post("/{incident_id}/generate-patch", response_model=IncidentPublic)
def generate_patch(incident_id: str, request: Request) -> IncidentPublic:
    return request.app.state.container.orchestrator.generate_patch(incident_id)


@router.post("/{incident_id}/validate", response_model=IncidentPublic)
def validate_incident(incident_id: str, request: Request) -> IncidentPublic:
    return request.app.state.container.orchestrator.validate(incident_id)


@router.post("/{incident_id}/triage", response_model=IncidentPublic)
def triage_incident(incident_id: str, request: Request) -> IncidentPublic:
    return request.app.state.container.orchestrator.triage_incident(incident_id)


@router.post("/{incident_id}/replay", response_model=IncidentPublic)
def replay_incident(incident_id: str, request: Request) -> IncidentPublic:
    return request.app.state.container.orchestrator.replay(incident_id)


@router.post("/{incident_id}/mitigate", response_model=IncidentPublic)
def propose_mitigation(incident_id: str, request: Request) -> IncidentPublic:
    return request.app.state.container.orchestrator.propose_mitigation(incident_id)


@router.post("/{incident_id}/postmortem", response_model=IncidentPublic)
def generate_postmortem(incident_id: str, request: Request) -> IncidentPublic:
    return request.app.state.container.orchestrator.postmortem(incident_id)
