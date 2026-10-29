from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status

from backend.app.api.deps import get_current_actor
from backend.app.models.schemas import IncidentCreate, IncidentPublic

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
