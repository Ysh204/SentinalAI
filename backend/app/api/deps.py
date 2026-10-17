"""FastAPI application container."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.config import Settings, load_settings
from backend.app.db.database import Database
from backend.app.repositories.incident_repository import IncidentRepository
from backend.app.services.ai_provider import get_provider
from backend.app.services.analyzer import Analyzer
from backend.app.services.approval_service import ApprovalService
from backend.app.services.incident_service import IncidentService
from backend.app.services.patcher import Patcher
from backend.app.services.validator import Validator
from backend.app.workflow.orchestrator import Orchestrator


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
    orchestrator = Orchestrator(
        incidents=incidents,
        analyzer=analyzer,
        patcher=patcher,
        validator=validator,
        approvals=ApprovalService(),
    )
    return AppContainer(
        settings=settings,
        database=database,
        incidents=incidents,
        orchestrator=orchestrator,
        provider_name=provider.name,
    )
