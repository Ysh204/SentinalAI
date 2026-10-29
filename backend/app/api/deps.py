"""FastAPI application container and dependencies."""

from __future__ import annotations

import hmac
from dataclasses import dataclass

from fastapi import Header, Query, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.app.core.config import Settings, load_settings
from backend.app.core.exceptions import SentinelAIError
from backend.app.db.database import Database
from backend.app.repositories.incident_repository import IncidentRepository
from backend.app.services.ai_provider import get_provider
from backend.app.services.analyzer import Analyzer
from backend.app.services.approval_service import ApprovalService
from backend.app.services.context_collector import ContextCollector
from backend.app.services.incident_service import IncidentService
from backend.app.services.mitigation import MitigationService
from backend.app.services.patcher import Patcher
from backend.app.services.postmortem import PostmortemService
from backend.app.services.replay_service import ReplayService
from backend.app.services.triage import TriageEngine
from backend.app.services.validator import Validator
from backend.app.workflow.orchestrator import Orchestrator

security = HTTPBearer(auto_error=False)


def _match_token(token: str, settings: Settings) -> str | None:
    """Constant-time lookup. Every configured key is compared so timing does not reveal which matched."""
    matched: str | None = None
    candidate = token.encode("utf-8")
    for expected, actor in settings.credentials:
        if hmac.compare_digest(candidate, expected.encode("utf-8")):
            matched = actor
    return matched


def _authenticate(request: Request, token: str | None) -> str:
    settings: Settings = request.app.state.container.settings
    if not settings.auth_enabled:
        return "anonymous"
    if not settings.credentials:
        # Fail closed: auth was requested but nothing can ever satisfy it.
        raise SentinelAIError(
            "Authentication is enabled but no API keys are configured.",
            code="auth_misconfigured",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    if not token:
        raise SentinelAIError(
            "Authentication required. Provide Authorization: Bearer <key> or X-API-Key header.",
            code="unauthorized",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    actor = _match_token(token, settings)
    if actor is None:
        raise SentinelAIError(
            "Invalid API credentials.",
            code="forbidden",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    return actor


def get_current_actor(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(security),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> str:
    """Identity comes from the key the server issued, never from anything the client claims."""
    token = credentials.credentials if credentials and credentials.credentials else x_api_key
    return _authenticate(request, token)


def get_stream_actor(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(security),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    access_token: str | None = Query(None),
) -> str:
    """Like get_current_actor, but also accepts ?access_token= because browser EventSource cannot send headers.

    Query tokens can end up in proxy/access logs: prefer a dedicated read-only key for the stream.
    """
    token = credentials.credentials if credentials and credentials.credentials else (x_api_key or access_token)
    return _authenticate(request, token)


def require_demo_mode(request: Request) -> None:
    if not request.app.state.container.settings.demo_mode:
        raise SentinelAIError("Demo endpoints are disabled (DEMO_MODE=false).", code="not_found", status_code=404)


@dataclass
class AppContainer:
    settings: Settings
    database: Database
    incidents: IncidentService
    orchestrator: Orchestrator
    provider_name: str


def build_container(settings: Settings | None = None) -> AppContainer:
    settings = settings or load_settings()
    database = Database(settings.database_path)
    repository = IncidentRepository(database)
    incidents = IncidentService(repository, settings)
    provider = get_provider(settings)
    analyzer = Analyzer(provider, settings)
    patcher = Patcher(provider, settings)
    validator = Validator(settings)
    collector = ContextCollector(settings)
    orchestrator = Orchestrator(
        incidents=incidents,
        analyzer=analyzer,
        patcher=patcher,
        validator=validator,
        approvals=ApprovalService(),
        triage=TriageEngine(provider, collector, settings),
        mitigation=MitigationService(settings),
        replay_service=ReplayService(settings, validator),
        postmortems=PostmortemService(provider),
    )
    return AppContainer(
        settings=settings,
        database=database,
        incidents=incidents,
        orchestrator=orchestrator,
        provider_name=provider.name,
    )
