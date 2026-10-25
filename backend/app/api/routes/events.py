from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from backend.app.models.incident import TERMINAL_STATUSES
from backend.app.models.schemas import MetricsResponse
from backend.app.services.eval_harness import SCENARIOS, score
from backend.app.services.events import hub

router = APIRouter(tags=["events"])


@router.get("/api/events")
async def incident_events() -> StreamingResponse:
    return StreamingResponse(hub.stream(), media_type="text/event-stream")


@router.get("/api/metrics", response_model=MetricsResponse)
def metrics(request: Request) -> MetricsResponse:
    incidents = request.app.state.container.incidents.list()
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


@router.post("/api/eval/run")
def run_eval(request: Request) -> dict:
    from victim_app import state

    container = request.app.state.container
    results = []
    for scenario in SCENARIOS:
        state.inject(scenario.mode)
        alert = scenario.alert.model_copy(update={"fingerprint": f"eval:{scenario.name}"})
        incident = container.incidents.ingest_alert(alert)
        incident = container.orchestrator.triage_incident(incident.id)
        results.append((scenario, incident))
    return score(results)
