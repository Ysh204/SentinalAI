"""Deterministic offline AI provider for local demos and tests."""

from __future__ import annotations

from backend.app.models.schemas import IncidentPublic
from backend.app.services.ai_provider import AIProvider, AnalysisDraft, PatchDraft

SAMPLE_PATCH = (
    "--- a/buggy_app.py\n"
    "+++ b/buggy_app.py\n"
    "@@ -4,3 +4,3 @@\n"
    " def add(left: int, right: int) -> int:\n"
    '     """Return the sum of two integers."""\n'
    "-    return left - right  # BUG: should add\n"
    "+    return left + right\n"
)


class MockProvider(AIProvider):
    name = "mock"

    def analyze_incident(self, incident: IncidentPublic, source_context: str) -> AnalysisDraft:
        looks_like_sample = (
            "add(" in incident.error_message.lower()
            or "buggy_app" in incident.stack_trace
            or "add(" in incident.stack_trace
            or "subtract" in source_context.lower()
            or "should add" in source_context
        )
        if looks_like_sample:
            return AnalysisDraft(
                hypothesis=(
                    "The failing assertion is consistent with `add()` returning a difference "
                    "instead of a sum. In the sample app, `add(left, right)` currently uses "
                    "subtraction (`left - right`). That would make `add(2, 3)` return `-1` "
                    "instead of `5`."
                ),
                suspected_file="buggy_app.py",
                suspected_function="add",
                confidence="high",
                recommended_next_steps=[
                    "Generate a unified diff that changes subtraction to addition in `add()`.",
                    "Apply the patch only in a disposable workspace.",
                    "Run the sample pytest suite and review the result before any approval.",
                ],
                provider=self.name,
            )
        return AnalysisDraft(
            hypothesis=(
                "The incident was ingested, but this offline mock provider only has a precise "
                "diagnosis for the included sample `add()` bug. Treat the following as a generic "
                "starting point: inspect the top stack frame, confirm the reported assertion, "
                "and gather surrounding source before proposing a patch."
            ),
            suspected_file=None,
            suspected_function=None,
            confidence="low",
            recommended_next_steps=[
                "Attach a repository path that contains the failing source.",
                "Re-run analysis with richer context, or switch AI_PROVIDER to gemini.",
                "Do not apply any patch without human review.",
            ],
            provider=self.name,
        )

    def generate_patch(self, incident: IncidentPublic, source_context: str) -> PatchDraft:
        sample_like = (
            (incident.root_cause_analysis and incident.root_cause_analysis.suspected_file == "buggy_app.py")
            or "buggy_app" in (incident.repository_path or "")
            or "return left - right" in source_context
            or "BUG: should add" in source_context
        )
        if not sample_like:
            return PatchDraft(
                unified_diff="",
                provider=self.name,
                notes="Mock provider has no deterministic patch for this incident.",
            )
        return PatchDraft(
            unified_diff=SAMPLE_PATCH.strip() + "\n",
            provider=self.name,
            notes="Deterministic patch for the sample add() bug.",
        )
