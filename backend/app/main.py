"""SentinelAI FastAPI entrypoint."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.deps import AppContainer, build_container
from backend.app.api.routes import approvals, health, incidents
from backend.app.core.config import Settings, load_settings
from backend.app.core.exceptions import SentinelAIError
from backend.app.core.logging import configure_logging


def create_app(settings: Settings | None = None, container: AppContainer | None = None) -> FastAPI:
    settings = settings or load_settings()
    configure_logging(settings)
    app = FastAPI(
        title="SentinelAI",
        description="AI-assisted incident response and code repair (local MVP). Not production-hardened.",
        version=settings.app_version,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:8501",
            "http://127.0.0.1:8501",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5174",
            "http://localhost:5175",
            "http://127.0.0.1:5175",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.container = container or build_container(settings)

    @app.exception_handler(SentinelAIError)
    async def handle_domain_error(_request: Request, exc: SentinelAIError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "code": exc.code},
        )

    app.include_router(health.router)
    app.include_router(incidents.router)
    app.include_router(approvals.router)
    return app


app = create_app()
