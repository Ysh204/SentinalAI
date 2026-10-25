"""Deterministic offline AI provider for local demos and tests."""

from __future__ import annotations

from backend.app.models.schemas import IncidentPublic, Verdict
from backend.app.services.ai_provider import AIProvider, AnalysisDraft, PatchDraft
from backend.app.services.triage_rules import apply_confidence_gate, classify

SAMPLE_PATCH = (
    "--- a/buggy_app.py\n"
    "+++ b/buggy_app.py\n"
    "@@ -4,3 +4,3 @@\n"
    " def add(left: int, right: int) -> int:\n"
    '     """Return the sum of two integers."""\n'
    "-    return left - right  # BUG: should add\n"
    "+    return left + right\n"
)

CHECKOUT_PATCH = (
    "--- a/shop.py\n"
    "+++ b/shop.py\n"
    "@@ -43,3 +43,5 @@\n"
    " def _line_total(item: dict[str, Any] | None) -> int:\n"
    "     # Intentional crash site for the code_bug injector: item may be None.\n"
    "-    return int(item[\"price\"]) * int(item[\"qty\"])\n"
    "+    if item is None:\n"
    "+        return 0\n"
    "+    return int(item[\"price\"]) * int(item[\"qty\"])\n"
)


class MockProvider(AIProvider):
    name = "mock"

    def analyze_incident(self, incident: IncidentPublic, source_context: str) -> AnalysisDraft:
        if self._looks_like_checkout(incident, source_context):
            return AnalysisDraft(
                hypothesis=(
                    "Checkout crashes when a cart line is None. `_line_total` indexes `item['price']` "
                    "without a null check, which matches TypeError: 'NoneType' object is not subscriptable."
                ),
                suspected_file="shop.py",
                suspected_function="_line_total",
                confidence="high",
                recommended_next_steps=[
                    "Generate a patch that guards None cart lines.",
                    "Run tests in a disposable workspace.",
                    "Replay the captured checkout request before/after.",
                ],
                provider=self.name,
            )
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
                "diagnosis for the included sample bugs. Treat the following as a generic "
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
        if self._looks_like_checkout(incident, source_context):
            return PatchDraft(
                unified_diff=CHECKOUT_PATCH,
                provider=self.name,
                notes="Guard None cart lines in _line_total.",
            )
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

    def triage_incident(self, incident: IncidentPublic, context: dict[str, Any]) -> Verdict:
        return apply_confidence_gate(classify(incident, context, self.name))

    def generate_postmortem(self, incident: IncidentPublic) -> str:
        verdict = incident.verdict
        category = verdict.category.value if verdict else "unknown"
        track = verdict.recommended_track.value if verdict else "unknown"
        action = ""
        if incident.mitigation and incident.mitigation.status == "executed":
            action = f"Simulated mitigation `{incident.mitigation.action}` was approved and executed."
        elif incident.replay and incident.replay.after_ok:
            action = "A sandbox patch replayed the captured request successfully (before failed, after passed)."
        elif incident.proposed_patch:
            action = "A patch was proposed; the original repository was not modified."
        evidence = "; ".join(verdict.evidence) if verdict else incident.error_message
        return (
            f"Root cause category: {category} ({track}). Evidence: {evidence}. {action} "
            "This report is generated in a demo environment with simulated adapters."
        )

    def _looks_like_checkout(self, incident: IncidentPublic, source_context: str) -> bool:
        hay = " ".join(
            [
                incident.error_message,
                incident.stack_trace,
                incident.repository_path or "",
                source_context,
                (incident.verdict.category.value if incident.verdict else ""),
            ]
        ).lower()
        return (
            "shop.py" in hay
            or "victim_app" in hay
            or "_line_total" in hay
            or "nonetype" in hay
            or (incident.verdict and incident.verdict.category.value == "code_bug")
        )
