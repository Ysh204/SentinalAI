"""Provider-independent AI interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from backend.app.core.config import Settings
from backend.app.core.exceptions import SentinelAIError
from backend.app.models.schemas import IncidentPublic

ANALYSIS_DISCLAIMER = (
    "AI-generated hypothesis, not verified fact. A human must review before any change."
)


@dataclass
class AnalysisDraft:
    hypothesis: str
    suspected_file: str | None = None
    suspected_function: str | None = None
    confidence: str = "medium"
    recommended_next_steps: list[str] = field(default_factory=list)
    provider: str = "unknown"
    source_files_considered: list[str] = field(default_factory=list)


@dataclass
class PatchDraft:
    unified_diff: str
    provider: str
    notes: str = ""


class AIProvider(ABC):
    name: str

    @abstractmethod
    def analyze_incident(self, incident: IncidentPublic, source_context: str) -> AnalysisDraft:
        raise NotImplementedError

    @abstractmethod
    def generate_patch(self, incident: IncidentPublic, source_context: str) -> PatchDraft:
        raise NotImplementedError


def get_provider(settings: Settings) -> AIProvider:
    from backend.app.services.providers.gemini_provider import GeminiProvider
    from backend.app.services.providers.mock_provider import MockProvider

    if settings.ai_provider in {"mock", "offline"}:
        return MockProvider()
    if settings.ai_provider == "gemini":
        if not settings.gemini_api_key:
            raise SentinelAIError(
                "AI_PROVIDER=gemini requires GEMINI_API_KEY in the environment.",
                code="provider_misconfigured",
                status_code=500,
            )
        return GeminiProvider(api_key=settings.gemini_api_key, model=settings.gemini_model)
    raise SentinelAIError(
        f"Unknown AI_PROVIDER '{settings.ai_provider}'. Use 'mock' or 'gemini'.",
        code="provider_misconfigured",
        status_code=500,
    )
