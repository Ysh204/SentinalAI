"""Root-cause analysis service. Output is always labeled as a hypothesis."""

from __future__ import annotations

import logging

from backend.app.core.exceptions import SentinelAIError
from backend.app.models.schemas import AnalysisResult, IncidentPublic
from backend.app.services.ai_provider import ANALYSIS_DISCLAIMER, AIProvider
from backend.app.services.source_context import collect_source_context, resolve_repository_path

LOGGER = logging.getLogger("sentinelai.analyzer")


class Analyzer:
    def __init__(self, provider: AIProvider, settings) -> None:
        self.provider = provider
        self.settings = settings

    def analyze(self, incident: IncidentPublic) -> AnalysisResult:
        repo = resolve_repository_path(incident.repository_path, self.settings)
        source_context, files = collect_source_context(repo)
        try:
            draft = self.provider.analyze_incident(incident, source_context)
        except SentinelAIError:
            raise
        except Exception as exc:
            LOGGER.exception("Analyzer provider failed")
            raise SentinelAIError(
                "Analysis provider failed. No diagnosis was stored as success.",
                code="analyzer_failed",
                status_code=502,
            ) from exc

        hypothesis = (draft.hypothesis or "").strip()
        if not hypothesis:
            raise SentinelAIError(
                "Analysis provider returned an empty hypothesis.",
                code="malformed_analysis",
                status_code=502,
            )
        confidence = draft.confidence if draft.confidence in {"low", "medium", "high"} else "medium"
        return AnalysisResult(
            hypothesis=hypothesis,
            suspected_file=draft.suspected_file,
            suspected_function=draft.suspected_function,
            confidence=confidence,
            recommended_next_steps=draft.recommended_next_steps or ["Review the hypothesis with a human."],
            disclaimer=ANALYSIS_DISCLAIMER,
            provider=draft.provider or self.provider.name,
            source_files_considered=draft.source_files_considered or files,
        )
