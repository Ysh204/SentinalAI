from fastapi import APIRouter, Request

from backend.app.models.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    container = request.app.state.container
    db_ok = container.database.path.exists()
    return HealthResponse(
        status="ok",
        app=container.settings.app_name,
        team=container.settings.team_name,
        version=container.settings.app_version,
        ai_provider=container.provider_name,
        gemini_configured=container.settings.gemini_configured,
        database_ready=db_ok,
    )
