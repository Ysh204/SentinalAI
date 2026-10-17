from fastapi import APIRouter, Request

from backend.app.models.schemas import ApproveRequest, IncidentPublic, RejectRequest

router = APIRouter(prefix="/api/incidents", tags=["approvals"])


@router.post("/{incident_id}/approve", response_model=IncidentPublic)
def approve_incident(
    incident_id: str,
    request: Request,
    payload: ApproveRequest | None = None,
) -> IncidentPublic:
    body = payload or ApproveRequest()
    return request.app.state.container.orchestrator.approve(incident_id, body)


@router.post("/{incident_id}/reject", response_model=IncidentPublic)
def reject_incident(incident_id: str, payload: RejectRequest, request: Request) -> IncidentPublic:
    return request.app.state.container.orchestrator.reject(incident_id, payload)
