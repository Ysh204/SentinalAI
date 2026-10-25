"""Triage engine: collect context, classify, refuse to guess when confidence is low."""

from __future__ import annotations

import logging

from backend.app.core.config import Settings
from backend.app.models.incident import RecommendedTrack
from backend.app.models.schemas import IncidentPublic, Verdict
from backend.app.services.ai_provider import AIProvider
from backend.app.services.context_collector import ContextCollector
from backend.app.services.triage_rules import LOW_CONFIDENCE, apply_confidence_gate, classify

LOGGER = logging.getLogger("sentinelai.triage")


class TriageEngine:
    def __init__(self, provider: AIProvider, collector: ContextCollector, settings: Settings) -> None:
        self.provider = provider
        self.collector = collector
        self.settings = settings

    def run(self, incident: IncidentPublic) -> tuple[Verdict, dict]:
        context = self.collector.collect(incident)
        try:
            verdict = self.provider.triage_incident(incident, context)
        except Exception:
            LOGGER.exception("Provider triage failed; using recorded demo rules")
            verdict = classify(incident, context, provider=f"{self.provider.name}-fallback")
        verdict = apply_confidence_gate(verdict)
        if verdict.confidence < LOW_CONFIDENCE:
            verdict.recommended_track = RecommendedTrack.ESCALATE
            verdict.escalate_to_human = True
        return verdict, context
