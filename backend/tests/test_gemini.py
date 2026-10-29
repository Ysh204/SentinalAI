"""Tests for GeminiProvider with a fake client to verify contract and patch generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from backend.app.core.exceptions import SentinelAIError
from backend.app.models.incident import IncidentStatus
from backend.app.models.schemas import IncidentPublic
from backend.app.services.ai_provider import PatchDraft
from backend.app.services.providers.gemini_provider import GeminiProvider


class FakeContentResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class FakeModels:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls = []

    def generate_content(self, model: str, contents: str):
        self.calls.append({"model": model, "contents": contents})
        if not self.responses:
            return FakeContentResponse("")
        return FakeContentResponse(self.responses.pop(0))


class FakeGenAIClient:
    def __init__(self, responses: list[str]) -> None:
        self.models = FakeModels(responses)


def _make_sample_incident() -> IncidentPublic:
    now = datetime.now(timezone.utc)
    return IncidentPublic(
        id="inc-test-123",
        title="TypeError: NoneType object has no attribute total",
        error_message="NoneType error in line_total",
        stack_trace="Traceback (most recent call last):\n  File 'victim_app/shop.py', line 50",
        repository_path="victim_app",
        service="checkout",
        status=IncidentStatus.RECEIVED,
        created_at=now,
        updated_at=now,
    )


def test_gemini_generate_patch_does_not_crash_on_disclaimer_kwarg() -> None:
    provider = GeminiProvider(api_key="fake-key", model="gemini-2.5-flash")
    fake_diff = "--- a/shop.py\n+++ b/shop.py\n@@ -10,1 +10,2 @@\n+if item is None: return 0\n"
    response_json = json.dumps({"unified_diff": fake_diff, "notes": "Fix None handling"})
    provider._client = FakeGenAIClient([response_json])

    incident = _make_sample_incident()
    patch_draft = provider.generate_patch(incident, "source code context")

    assert isinstance(patch_draft, PatchDraft)
    assert patch_draft.provider == "gemini"
    assert patch_draft.notes == "Fix None handling"
    assert "if item is None" in patch_draft.unified_diff


def test_gemini_analyze_incident() -> None:
    provider = GeminiProvider(api_key="fake-key", model="gemini-2.5-flash")
    response_json = json.dumps({
        "hypothesis": "Item in cart is None causing crash",
        "suspected_file": "victim_app/shop.py",
        "suspected_function": "_line_total",
        "confidence": "high",
        "recommended_next_steps": ["check cart item nullability"],
    })
    provider._client = FakeGenAIClient([response_json])

    incident = _make_sample_incident()
    analysis = provider.analyze_incident(incident, "source code context")

    assert analysis.hypothesis == "Item in cart is None causing crash"
    assert analysis.suspected_file == "victim_app/shop.py"
    assert analysis.confidence == "high"
    assert analysis.provider == "gemini"


def test_gemini_empty_response_raises_502() -> None:
    provider = GeminiProvider(api_key="fake-key", model="gemini-2.5-flash")
    provider._client = FakeGenAIClient([""])

    incident = _make_sample_incident()
    with pytest.raises(SentinelAIError) as exc_info:
        provider.generate_patch(incident, "source code")
    assert exc_info.value.status_code == 502


def test_gemini_client_exception_raises_502() -> None:
    provider = GeminiProvider(api_key="fake-key", model="gemini-2.5-flash")
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("API connection timeout")
    provider._client = mock_client

    incident = _make_sample_incident()
    with pytest.raises(SentinelAIError) as exc_info:
        provider.generate_patch(incident, "source code")
    assert exc_info.value.status_code == 502
