from fastapi import APIRouter, Request, status

from backend.app.models.schemas import AlertCreate, BreakRequest, IncidentPublic

router = APIRouter(tags=["alerts"])


@router.post("/api/alerts", response_model=IncidentPublic, status_code=status.HTTP_201_CREATED)
def ingest_alert(payload: AlertCreate, request: Request) -> IncidentPublic:
    container = request.app.state.container
    incident = container.incidents.ingest_alert(payload)
    if incident.occurrence_count == 1:
        return container.orchestrator.triage_incident(incident.id)
    return incident


@router.post("/api/demo/break", response_model=IncidentPublic)
def break_checkout(payload: BreakRequest, request: Request) -> IncidentPublic:
    return _break_and_ingest(request.app.state.container, payload.mode)


@router.post("/api/demo/simulate", response_model=IncidentPublic)
def simulate_incident(request: Request) -> IncidentPublic:
    return ingest_alert(
        AlertCreate(
            source="simulate",
            service="checkout",
            title="Simulated payments outage",
            error_message="Payments API unavailable",
            stack_trace="",
            endpoint="/checkout",
            status_code=503,
            logs=["14 timeouts to payments API in 2 min", "no deploy in last 6h"],
            captured_request={
                "method": "POST",
                "path": "/checkout",
                "status_code": 503,
                "body": {"order_id": "ord-1001"},
            },
        ),
        request,
    )


def _break_and_ingest(container, mode: str) -> IncidentPublic:
    import httpx

    from victim_app import state
    from victim_app.redact import redact
    from victim_app.shop import SAMPLE_CART, _run_checkout

    url = container.settings.victim_app_url.rstrip("/")
    error = f"injected {mode}"
    stack = ""
    status_code = 500
    captured = {"method": "POST", "path": "/checkout", "body": redact(SAMPLE_CART)}
    logs: list[str] = []

    if url == "inline":
        state.inject(mode)
        try:
            _run_checkout(dict(SAMPLE_CART))
            error = f"checkout still succeeding after inject {mode}"
            status_code = 200
        except Exception as exc:
            import traceback

            state.record_result(False)
            error = str(exc)
            stack = traceback.format_exc()
            status_code = 503 if "unavailable" in error.lower() else 401 if "key" in error.lower() else 500
        logs = state.snapshot()["logs"][-20:]
        captured["status_code"] = status_code
        captured["inject"] = mode
    else:
        try:
            httpx.post(f"{url}/control/inject", json={"mode": mode}, timeout=3.0)
            response = httpx.post(f"{url}/checkout", json=SAMPLE_CART, timeout=3.0)
            status_code = response.status_code
            body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            error = str(body.get("detail") or body or f"HTTP {status_code}")
            captured["status_code"] = status_code
            captured["inject"] = mode
            ctx = httpx.get(f"{url}/control/context", timeout=2.0)
            if ctx.status_code == 200:
                logs = list(ctx.json().get("recent_logs") or [])
        except httpx.HTTPError:
            state.inject(mode)
            state.record_result(False)
            error = f"shop unreachable; injected {mode} locally"
            logs = state.snapshot()["logs"][-20:]
            captured["inject"] = mode

    incident = container.incidents.ingest_alert(
        AlertCreate(
            source="demo",
            service="checkout",
            title=f"Break checkout: {mode}",
            error_message=error,
            stack_trace=stack,
            endpoint="/checkout",
            status_code=status_code,
            captured_request=captured,
            logs=logs,
            repository_path="victim_app",
        )
    )
    if incident.occurrence_count == 1:
        return container.orchestrator.triage_incident(incident.id)
    return incident
