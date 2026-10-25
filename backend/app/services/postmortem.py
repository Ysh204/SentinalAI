"""Turn the incident timeline into a readable report."""

from __future__ import annotations

from datetime import datetime, timezone

from backend.app.models.schemas import IncidentPublic, Postmortem
from backend.app.services.ai_provider import AIProvider


class PostmortemService:
    def __init__(self, provider: AIProvider) -> None:
        self.provider = provider

    def generate(self, incident: IncidentPublic) -> Postmortem:
        try:
            summary = self.provider.generate_postmortem(incident)
        except Exception:
            summary = _fallback_summary(incident)
        items = [
            "Keep the human approval gate for any change that touches production.",
            "Confirm the demo shop error rate stayed down after the action.",
        ]
        if incident.verdict and incident.verdict.category.value == "code_bug":
            items.append("Review the sandbox patch; do not merge without a human.")
        if incident.mitigation:
            items.append("Replace simulated adapters with real ones before any non-demo use.")
        return Postmortem(
            summary=summary,
            root_cause=(
                incident.verdict.category.value if incident.verdict else "unknown"
            ),
            action_items=items,
            provider=self.provider.name,
            generated_at=datetime.now(timezone.utc),
        )


def _fallback_summary(incident: IncidentPublic) -> str:
    events = ", ".join(f"{item.event}" for item in incident.history[-8:])
    return f"Incident {incident.title} timeline: {events}."
