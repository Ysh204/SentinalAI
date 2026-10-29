"""SentinelAI FastAPI entrypoint."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.deps import AppContainer, build_container
from backend.app.api.routes import alerts, approvals, events, health, incidents
from backend.app.core.config import Settings, load_settings
from backend.app.core.exceptions import SentinelAIError
from backend.app.core.logging import configure_logging
from backend.app.services.events import hub
from backend.app.services.health_watcher import HealthWatcher

LOGGER = logging.getLogger("sentinelai")


def create_app(settings: Settings | None = None, container: AppContainer | None = None) -> FastAPI:
    settings = settings or load_settings()
    if settings.auth_enabled and not settings.credentials:
        raise RuntimeError("AUTH_ENABLED is set but no API key is configured (set API_KEYS or SENTINEL_API_KEY).")
    configure_logging(settings)
    container = container or build_container(settings)
    if not settings.auth_enabled:
        LOGGER.warning("Authentication is DISABLED: every endpoint is open. Set API_KEYS before exposing this service.")
    if settings.sandbox_mode != "docker":
        LOGGER.warning(
            "SANDBOX_MODE=%s: patch tests run directly on this host. Use docker for untrusted patches.",
            settings.sandbox_mode,
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.container = container
        hub.set_loop(asyncio.get_running_loop())
        # Recover any stale in-progress incidents from unclean shutdowns
        try:
            container.orchestrator.recover_stuck_incidents()
        except Exception:
            pass

        async def _periodic_sweep():
            while True:
                try:
                    await asyncio.sleep(max(10, container.settings.health_check_interval))
                    container.orchestrator.recover_stuck_incidents(container.settings.stuck_timeout_seconds)
                except asyncio.CancelledError:
                    break
                except Exception:
                    LOGGER.exception("Periodic stuck-incident recovery failed")

        sweep_task = asyncio.create_task(_periodic_sweep())
        watcher: HealthWatcher | None = None
        if container.settings.health_watcher_enabled:
            watcher = HealthWatcher(container)
            watcher.start()
        yield
        sweep_task.cancel()
        if watcher:
            watcher.stop()

    app = FastAPI(
        title="SentinelAI",
        description="AI-assisted incident response for web services (local demo).",
        version=settings.app_version,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
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
