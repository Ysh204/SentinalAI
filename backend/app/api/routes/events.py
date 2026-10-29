from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from backend.app.api.deps import get_current_actor, get_stream_actor, require_demo_mode
from backend.app.models.incident import TERMINAL_STATUSES
from backend.app.models.schemas import MetricsResponse
from backend.app.services.eval_harness import SCENARIOS, score
from backend.app.services.events import hub

router = APIRouter(tags=["events"])


@router.get("/api/events")
async def incident_events(_actor: str = Depends(get_stream_actor)) -> StreamingResponse:
    return StreamingResponse(hub.stream(), media_type="text/event-stream")


@router.get("/api/metrics", response_model=MetricsResponse)
def metrics(request: Request, _actor: str = Depends(get_current_actor)) -> MetricsResponse:
    incidents = request.app.state.container.incidents.list_all()
    by_status: dict[str, int] = {}
    by_category: dict[str, int] = {}
    durations: list[float] = []
    open_count = 0
    for item in incidents:
        by_status[item.status.value] = by_status.get(item.status.value, 0) + 1
        if item.verdict:
            key = item.verdict.category.value
            by_category[key] = by_category.get(key, 0) + 1
        if item.status in TERMINAL_STATUSES or item.status.value in {"MITIGATED", "PATCH_VERIFIED"}:
            durations.append((item.updated_at - item.created_at).total_seconds())
        if item.status not in TERMINAL_STATUSES:
            open_count += 1
    mean = round(sum(durations) / len(durations), 2) if durations else None
    return MetricsResponse(
        incidents_total=len(incidents),
        by_status=by_status,
        by_category=by_category,
        mean_time_to_resolution_seconds=mean,
        open_count=open_count,
    )


@router.post("/api/eval/run", dependencies=[Depends(get_current_actor), Depends(require_demo_mode)])
def run_eval(request: Request) -> dict:
    import uuid

    from victim_app import state

    container = request.app.state.container
    run_id = uuid.uuid4().hex[:8]
    results = []
    for scenario in SCENARIOS:
        # Reset shop state. Do not inject the expected failure_mode — that was
        # leaking the answer key into triage via context.victim.failure_mode.
        state.inject("none")
        alert = scenario.alert.model_copy(update={"fingerprint": f"eval:{run_id}:{scenario.name}"})
        incident = container.incidents.ingest_alert(alert)
        incident = container.orchestrator.triage_incident(incident.id)
        results.append((scenario, incident))
    return score(results)
