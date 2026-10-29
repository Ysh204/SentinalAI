from fastapi import APIRouter, Depends, Request

from backend.app.api.deps import get_current_actor
from backend.app.models.schemas import ApproveRequest, IncidentPublic, RejectRequest

router = APIRouter(
    prefix="/api/incidents",
    tags=["approvals"],
    dependencies=[Depends(get_current_actor)],
)


@router.post("/{incident_id}/approve", response_model=IncidentPublic)
def approve_incident(
    incident_id: str,
    request: Request,
    payload: ApproveRequest | None = None,
    actor: str = Depends(get_current_actor),
) -> IncidentPublic:
    body = payload or ApproveRequest()
    if actor != "anonymous":
        body = body.model_copy(update={"actor": actor})
    return request.app.state.container.orchestrator.approve(incident_id, body)


@router.post("/{incident_id}/reject", response_model=IncidentPublic)
def reject_incident(
    incident_id: str,
    payload: RejectRequest,
    request: Request,
    actor: str = Depends(get_current_actor),
) -> IncidentPublic:
    if actor != "anonymous":
        payload = payload.model_copy(update={"actor": actor})
    return request.app.state.container.orchestrator.reject(incident_id, payload)
