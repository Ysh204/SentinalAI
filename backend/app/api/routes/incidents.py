from fastapi import APIRouter, Request, status

from backend.app.models.schemas import IncidentCreate, IncidentPublic

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


@router.post("", response_model=IncidentPublic, status_code=status.HTTP_201_CREATED)
def create_incident(payload: IncidentCreate, request: Request) -> IncidentPublic:
    return request.app.state.container.incidents.create(payload)


@router.get("", response_model=list[IncidentPublic])
def list_incidents(request: Request) -> list[IncidentPublic]:
    return request.app.state.container.incidents.list()


@router.get("/{incident_id}", response_model=IncidentPublic)
def get_incident(incident_id: str, request: Request) -> IncidentPublic:
    return request.app.state.container.incidents.get(incident_id)


@router.post("/{incident_id}/analyze", response_model=IncidentPublic)
def analyze_incident(incident_id: str, request: Request) -> IncidentPublic:
    return request.app.state.container.orchestrator.analyze(incident_id)


@router.post("/{incident_id}/generate-patch", response_model=IncidentPublic)
def generate_patch(incident_id: str, request: Request) -> IncidentPublic:
    return request.app.state.container.orchestrator.generate_patch(incident_id)


@router.post("/{incident_id}/validate", response_model=IncidentPublic)
def validate_incident(incident_id: str, request: Request) -> IncidentPublic:
    return request.app.state.container.orchestrator.validate(incident_id)
