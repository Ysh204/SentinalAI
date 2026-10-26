"""SentinelAI FastAPI entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.deps import AppContainer, build_container
from backend.app.api.routes import alerts, approvals, events, health, incidents
from backend.app.core.config import Settings, load_settings
from backend.app.core.exceptions import SentinelAIError
from backend.app.core.logging import configure_logging
from backend.app.services.health_watcher import HealthWatcher


def create_app(settings: Settings | None = None, container: AppContainer | None = None) -> FastAPI:
    settings = settings or load_settings()
    configure_logging(settings)
    container = container or build_container(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.container = container
        watcher: HealthWatcher | None = None
        if container.settings.health_watcher_enabled:
            watcher = HealthWatcher(container)
            watcher.start()
        yield
        if watcher:
            watcher.stop()

    app = FastAPI(
        title="SentinelAI",
        description="AI-assisted incident response for web services (local demo). Not production-hardened.",
        version=settings.app_version,
        lifespan=lifespan,
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
    app.state.container = container

    @app.exception_handler(SentinelAIError)
    async def handle_domain_error(_request: Request, exc: SentinelAIError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "code": exc.code},
        )

    app.include_router(health.router)
    app.include_router(alerts.router)
    app.include_router(events.router)
    app.include_router(incidents.router)
    app.include_router(approvals.router)
    return app


app = create_app()
