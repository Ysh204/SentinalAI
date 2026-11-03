"""Deterministic offline AI provider for local demos and tests."""

from __future__ import annotations

from typing import Any

from backend.app.models.incident import VerdictCategory
from backend.app.models.schemas import IncidentPublic, Verdict
from backend.app.services.ai_provider import AIProvider, AnalysisDraft, PatchDraft
from backend.app.services.heuristic_patch import synthesize
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
        category = incident.verdict.category if incident.verdict else None
        error = incident.error_message.lower()
        title = incident.title.lower()
        stack = (incident.stack_trace or "").lower()

        # 1. Dependency Outage (e.g. Payments API 503)
        if (
            category == VerdictCategory.DEPENDENCY_OUTAGE
            or "503" in error
            or "payments" in error
            or "circuit breaker" in error
            or "charge processor" in error
            or "timeout" in error
        ):
            return AnalysisDraft(
                hypothesis=(
                    "The checkout service is suffering from an upstream dependency outage. The payments "
                    "gateway API is unreachable or returning 503 timeouts. Application code in shop.py "
                    "is healthy, but credit card charges cannot complete while the external service is down."
                ),
                suspected_file="shop.py",
                suspected_function="_charge_payments",
                confidence="high",
                recommended_next_steps=[
                    "Do not apply a code patch; application logic is not the root cause.",
                    "Execute simulated mitigation to enable cash-on-delivery fallback.",
                    "Monitor payment processor status endpoint until service recovers.",
                ],
                provider=self.name,
            )

        # 2. Bad Deployment (e.g. Bad deploy raises 500s)
        if (
            category == VerdictCategory.BAD_DEPLOY
            or "bad-2.0.0" in error
            or "after deploy" in error
            or "release" in title
            or "runtimeerror" in error
        ):
            return AnalysisDraft(
                hypothesis=(
                    "A critical regression was introduced in release revision `bad-2.0.0`. The new checkout "
                    "handler raises an unhandled RuntimeError on all paid orders. This is a release fault, "
                    "requiring an immediate rollback."
                ),
                suspected_file="shop.py",
                suspected_function="_run_checkout",
                confidence="high",
                recommended_next_steps=[
                    "Do not attempt live code patches on broken revision `bad-2.0.0`.",
                    "Execute simulated mitigation to rollback checkout to previous release `good-1.0.0`.",
                    "Verify error rate drops to zero after rollback execution.",
                ],
                provider=self.name,
            )

        # 3. Configuration / Expired Key
        if (
            category == VerdictCategory.CONFIG
            or "401" in error
            or "expired" in error
            or "invalid api key" in error
            or "rotation" in error
        ):
            return AnalysisDraft(
                hypothesis=(
                    "The payments integration credential (`payments_api_key`) has expired or failed "
                    "authentication (HTTP 401). Upstream payment authorization rejected the request "
                    "because the key rotation window was missed."
                ),
                suspected_file="shop.py",
                suspected_function="_charge_payments",
                confidence="high",
                recommended_next_steps=[
                    "Restore valid API credentials via control configuration (/control/restore-config).",
                    "Verify payment processing resumes with HTTP 200.",
                ],
                provider=self.name,
            )

        # 4. Resource / Memory Pressure
        if (
            category == VerdictCategory.RESOURCE
            or "memory" in error
            or "heap" in error
            or "oom" in error
            or "rss" in error
        ):
            return AnalysisDraft(
                hypothesis=(
                    "The checkout worker process is experiencing severe heap exhaustion / memory pressure. "
                    "Memory consumption exceeded the safety threshold (> 2MB), causing latency "
                    "and health check failures."
                ),
                suspected_file="shop.py",
                suspected_function="_run_checkout",
                confidence="high",
                recommended_next_steps=[
                    "Execute process restart via simulated mitigation (/control/restart) to flush heap.",
                    "Inspect memory sink telemetry and monitor post-restart RSS.",
                ],
                provider=self.name,
            )

        # 5. Sample App Arithmetic Bug
        looks_like_sample = (
            "add(" in error
            or "buggy_app" in stack
            or "add(" in stack
            or "subtract" in source_context.lower()
            or "should add" in source_context
            or "buggy_app" in (incident.repository_path or "")
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

        # 6. Checkout Code Bug (TypeError in _line_total)
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
                    "Generate a patch that guards None cart lines in _line_total.",
                    "Run tests in a disposable workspace.",
                    "Replay the captured checkout request before/after.",
                ],
                provider=self.name,
            )

        return AnalysisDraft(
            hypothesis=(
                "The incident was ingested, but this offline mock provider only has a precise "
                "diagnosis for the included sample bugs and checkout demo scenarios. Treat the following as a generic "
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
        category = incident.verdict.category if incident.verdict else None

        # Do not propose code patches for operational/mitigation incidents!
        if category in {
            VerdictCategory.DEPENDENCY_OUTAGE,
            VerdictCategory.BAD_DEPLOY,
            VerdictCategory.CONFIG,
            VerdictCategory.RESOURCE,
        }:
            action = incident.verdict.recommended_action if incident.verdict else "mitigation"
            return PatchDraft(
                unified_diff="",
                provider=self.name,
                notes=(
                    f"No code patch applicable: incident is triaged as {category.value} (Track 1: Mitigation). "
                    f"Recommended action is '{action}'. Execute simulated mitigation on the Overview tab "
                    "instead of modifying source code."
                ),
            )

        synthesized = synthesize(source_context, incident)
        if synthesized:
            diff, notes = synthesized
            return PatchDraft(unified_diff=diff, provider=self.name, notes=notes)

        if self._looks_like_checkout(incident, source_context):
            return PatchDraft(
                unified_diff=CHECKOUT_PATCH,
                provider=self.name,
                notes=(
                    "Offline fixture: guard None cart lines in _line_total. "
                    "Set AI_PROVIDER=gemini to synthesize a patch from a live model."
                ),
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
                notes=(
                    "Mock provider has no patch for this incident. "
                    "Set AI_PROVIDER=gemini with GEMINI_API_KEY to generate one."
                ),
            )
        return PatchDraft(
            unified_diff=SAMPLE_PATCH.strip() + "\n",
            provider=self.name,
            notes=(
                "Offline fixture for the sample add() bug. "
                "Set AI_PROVIDER=gemini to synthesize a patch from a live model."
            ),
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
        category = incident.verdict.category if incident.verdict else None
        if category and category != VerdictCategory.CODE_BUG:
            return False
        hay = " ".join([incident.error_message, incident.stack_trace or ""]).lower()
        return (
            "nonetype" in hay
            or "typeerror" in hay
            or "_line_total" in hay
            or (category == VerdictCategory.CODE_BUG)
        )
