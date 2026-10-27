from datetime import datetime, timezone
from dataclasses import replace

import pytest

from backend.app.core.exceptions import SentinelAIError
from backend.app.models.incident import RecommendedTrack, VerdictCategory
from backend.app.models.schemas import IncidentPublic, Verdict
from backend.app.services.mitigation import MitigationService
from backend.app.services.sandbox import sandbox_env
from backend.app.services.triage_rules import classify, observable_victim


def _incident(**kwargs) -> IncidentPublic:
    now = datetime.now(timezone.utc)
    payload = {
        "id": "00000000-0000-0000-0000-000000000099",
        "title": "t",
        "error_message": "e",
        "stack_trace": "",
        "repository_path": "victim_app",
        "status": "RECEIVED",
        "created_at": now,
        "updated_at": now,
    }
    payload.update(kwargs)
    return IncidentPublic(**payload)


def test_observable_victim_strips_injector_label() -> None:
    cleaned = observable_victim(
        {
            "victim": {
                "failure_mode": "code_bug",
                "recent_logs": ["ok", "injected failure_mode=code_bug", "checkout crash"],
                "deploy_version": "good-1.0.0",
            }
        }
    )
    assert "failure_mode" not in cleaned
    assert "injected failure_mode=code_bug" not in cleaned["recent_logs"]
    assert "checkout crash" in cleaned["recent_logs"]


def test_observable_victim_handles_direct_victim_dict() -> None:
    cleaned = observable_victim(
        {
            "failure_mode": "bad_deploy",
            "deploy_version": "bad-2.0.0",
            "recent_logs": ["booting", "injected failure_mode=bad_deploy", "500 error"],
            "dependency_health": {"payments": "up"},
        }
    )
    assert "failure_mode" not in cleaned
    assert "injected failure_mode=bad_deploy" not in cleaned["recent_logs"]
    assert "500 error" in cleaned["recent_logs"]
    assert cleaned["deploy_version"] == "bad-2.0.0"
    assert cleaned["dependency_health"]["payments"] == "up"


def test_triage_does_not_read_failure_mode_answer_key() -> None:
    incident = _incident(error_message="users are mildly annoyed", logs=["nothing useful"])
    verdict = classify(
        incident,
        {"victim": {"failure_mode": "code_bug", "dependency_health": {"payments": "up"}}},
        "test",
    )
    assert verdict.category == VerdictCategory.UNKNOWN
    assert verdict.escalate_to_human is True


def test_triage_infers_code_bug_from_stack_not_mode() -> None:
    incident = _incident(
        title="pricing crash",
        error_message="TypeError: 'NoneType' object is not subscriptable",
        stack_trace='File "shop.py", line 45, in _line_total\n    return int(item["price"])',
        logs=["checkout crash while summing line items"],
    )
    verdict = classify(
        incident,
        {"victim": {"failure_mode": "payments_outage", "dependency_health": {"payments": "down"}}},
        "test",
    )
    assert verdict.category == VerdictCategory.CODE_BUG
    assert verdict.recommended_action == "patch"


def test_sandbox_env_does_not_leak_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "secret-gemini")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret-aws")
    monkeypatch.setenv("OPENAI_API_KEY", "secret-openai")
    env = sandbox_env(".")
    assert "GEMINI_API_KEY" not in env
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert "OPENAI_API_KEY" not in env
    assert env["PYTHONPATH"] == "."


def test_mitigation_raises_when_victim_unreachable(tmp_settings) -> None:
    settings = replace(tmp_settings, victim_app_url="http://127.0.0.1:59999")
    service = MitigationService(settings)
    incident = _incident(
        status="MITIGATION_PROPOSED",
        verdict=Verdict(
            category=VerdictCategory.DEPENDENCY_OUTAGE,
            confidence=0.9,
            recommended_track=RecommendedTrack.MITIGATION,
            recommended_action="fallback",
            provider="mock",
        ),
    )
    with pytest.raises(SentinelAIError) as exc:
        service.execute(incident, "tester")
    assert exc.value.code == "victim_unreachable"


def test_mitigation_flat_error_rate_is_not_recovered(tmp_settings, monkeypatch: pytest.MonkeyPatch) -> None:
    service = MitigationService(tmp_settings)
    monkeypatch.setattr(service, "_error_rate", lambda: 1.0)
    monkeypatch.setattr(service, "_call", lambda action: None)
    monkeypatch.setattr(service, "_probe_error_rate", lambda: 1.0)
    incident = _incident(
        status="MITIGATION_PROPOSED",
        verdict=Verdict(
            category=VerdictCategory.DEPENDENCY_OUTAGE,
            confidence=0.9,
            recommended_track=RecommendedTrack.MITIGATION,
            recommended_action="fallback",
            provider="mock",
        ),
    )
    record = service.execute(incident, "tester")
    assert record.recovered is False
    assert record.error_rate_before == 1.0
    assert record.error_rate_after == 1.0
