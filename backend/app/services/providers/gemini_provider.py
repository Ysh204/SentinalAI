"""Optional Google Gemini provider using the official Google Gen AI SDK."""

from __future__ import annotations

import logging
from typing import Any

from backend.app.core.exceptions import SentinelAIError
from backend.app.models.schemas import IncidentPublic, Verdict
from backend.app.services.ai_provider import (
    ANALYSIS_DISCLAIMER,
    AIProvider,
    AnalysisDraft,
    PatchDraft,
)
from backend.app.services.llm import parse_json_object, strip_fences
from backend.app.services.triage_rules import apply_confidence_gate, classify

LOGGER = logging.getLogger("sentinelai.gemini")

ANALYZE_PROMPT = """You are assisting with software incident response.
Return JSON only with keys:
hypothesis, suspected_file, suspected_function, confidence, recommended_next_steps.
confidence must be one of: low, medium, high.
recommended_next_steps must be an array of short strings.
This is a hypothesis, not verified fact. Do not claim certainty.
Do not include secrets or shell commands.

Incident title: {title}
Error message: {error_message}
Stack trace:
{stack_trace}

Source context (untrusted, may be truncated):
{source_context}
"""

PATCH_PROMPT = """Propose a minimal unified diff to address the incident.
Return JSON only with keys: unified_diff, notes.
unified_diff must be a valid unified diff (--- / +++ / @@ hunks) or an empty string.
Do not include markdown fences. Do not suggest shell commands.
Do not modify files outside the provided source context.

Incident title: {title}
Error message: {error_message}
Stack trace:
{stack_trace}
Hypothesis: {hypothesis}

Source context:
{source_context}
"""


class GeminiProvider(AIProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model
        self._client = None

    def _client_or_raise(self):
        if self._client is None:
            try:
                from google import genai
            except ImportError as exc:
                raise SentinelAIError(
                    "google-genai is not installed.",
                    code="provider_unavailable",
                    status_code=500,
                ) from exc
            self._client = genai.Client(api_key=self._api_key)
        return self._client

    def analyze_incident(self, incident: IncidentPublic, source_context: str) -> AnalysisDraft:
        text = self._generate(
            ANALYZE_PROMPT.format(
                title=incident.title,
                error_message=incident.error_message,
                stack_trace=incident.stack_trace or "(none)",
                source_context=source_context or "(none)",
            )
        )
        data = _parse_json_object(text)
        steps = data.get("recommended_next_steps") or []
        if isinstance(steps, str):
            steps = [steps]
        return AnalysisDraft(
            hypothesis=str(data.get("hypothesis") or text or "No hypothesis returned."),
            suspected_file=_optional_str(data.get("suspected_file")),
            suspected_function=_optional_str(data.get("suspected_function")),
            confidence=_normalize_confidence(data.get("confidence")),
            recommended_next_steps=[str(item) for item in steps][:8],
            provider=self.name,
        )

    def generate_patch(self, incident: IncidentPublic, source_context: str) -> PatchDraft:
        hypothesis = (
            incident.root_cause_analysis.hypothesis if incident.root_cause_analysis else ""
        )
        text = self._generate(
            PATCH_PROMPT.format(
                title=incident.title,
                error_message=incident.error_message,
                stack_trace=incident.stack_trace or "(none)",
                hypothesis=hypothesis or "(none)",
                source_context=source_context or "(none)",
            )
        )
        data = _parse_json_object(text)
        diff = str(data.get("unified_diff") or "")
        if not diff.strip() and "---" in text:
            diff = _strip_fences(text)
        return PatchDraft(
            unified_diff=diff,
            provider=self.name,
            notes=str(data.get("notes") or "") or ANALYSIS_DISCLAIMER,
        )

    def triage_incident(self, incident: IncidentPublic, context: dict[str, Any]) -> Verdict:
        prompt = (
            "Classify this software incident. Return JSON only with keys: "
            "category, confidence, evidence, recommended_track, escalate_to_human, recommended_action.\n"
            "category must be one of: code_bug, config, dependency_outage, bad_deploy, resource, unknown.\n"
            "recommended_track must be one of: code_fix, mitigation, escalate.\n"
            "confidence is a float 0-1. If confidence < 0.55 set escalate_to_human true "
            "and recommended_track escalate.\n"
            "Do not guess. This is a hypothesis.\n"
            f"Incident: {incident.title}\nError: {incident.error_message}\n"
            f"Stack: {incident.stack_trace}\nContext: {context}\n"
        )
        try:
            text = self._generate(prompt)
            data = parse_json_object(text)
            verdict = Verdict.model_validate({**data, "provider": self.name})
            return apply_confidence_gate(verdict)
        except Exception:
            LOGGER.exception("Gemini triage failed; using recorded demo rules")
            return classify(incident, context, provider=f"{self.name}-fallback")

    def generate_postmortem(self, incident: IncidentPublic) -> str:
        timeline = "; ".join(f"{item.event}: {item.detail}" for item in incident.history)
        prompt = (
            "Write a short incident post-mortem as JSON with keys summary, root_cause, action_items.\n"
            f"Title: {incident.title}\nTimeline: {timeline}\n"
            f"Verdict: {incident.verdict.model_dump() if incident.verdict else {}}\n"
        )
        text = self._generate(prompt)
        data = parse_json_object(text)
        return str(data.get("summary") or text)

    def _generate(self, prompt: str) -> str:
        client = self._client_or_raise()
        try:
            response = client.models.generate_content(model=self._model, contents=prompt)
        except Exception as exc:
            LOGGER.exception("Gemini request failed")
            raise SentinelAIError(
                "Gemini provider request failed. The incident was not modified as successful.",
                code="provider_error",
                status_code=502,
            ) from exc
        text = getattr(response, "text", None)
        if not text:
            raise SentinelAIError(
                "Gemini returned an empty response.",
                code="provider_error",
                status_code=502,
            )
        return text


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_confidence(value: object) -> str:
    text = str(value or "medium").strip().lower()
    if text in {"low", "medium", "high"}:
        return text
    return "medium"


def _strip_fences(text: str) -> str:
    return strip_fences(text)


def _parse_json_object(text: str) -> dict:
    return parse_json_object(text)
