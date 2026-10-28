"""FastAPI application container and dependencies."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Header, Request, Security, status
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


def get_current_actor(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(security),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> str:
    container: AppContainer = request.app.state.container
    settings = container.settings

    if not settings.auth_enabled:
        return "anonymous"

    expected_key = settings.api_key
    if not expected_key:
        return "anonymous"

    token: str | None = None
    if credentials and credentials.credentials:
        token = credentials.credentials
    elif x_api_key:
        token = x_api_key

    if not token:
        raise SentinelAIError(
            "Authentication required. Provide Authorization: Bearer <key> or X-API-Key header.",
            code="unauthorized",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    key_part = token
    actor_part = "authenticated-user"
    if ":" in token:
        key_part, actor_part = token.split(":", 1)

    if key_part != expected_key:
        raise SentinelAIError(
            "Invalid API credentials.",
            code="forbidden",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    return actor_part


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
