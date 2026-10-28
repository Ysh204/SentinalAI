import threading
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend.app.core.exceptions import SentinelAIError
from backend.app.models.incident import RecommendedTrack, VerdictCategory
from backend.app.models.schemas import IncidentPublic, Verdict
from backend.app.services.diff_utils import apply_unified_diff, parse_file_patches
from backend.app.services.events import EventHub
from backend.app.services.mitigation import MitigationService
from backend.app.services.sandbox import sandbox_env
from backend.app.services.source_context import resolve_repository_path
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


def test_triage_word_boundary_avoids_false_positives() -> None:
    # "ord-4012" should NOT be classified as CONFIG
    incident_deadlock = _incident(
        title="DB Deadlock",
        error_message="DB deadlock on order ord-4012",
        stack_trace="",
        logs=["lock wait timeout exceeded on ord-4012"],
    )
    verdict1 = classify(incident_deadlock, {}, "test")
    assert verdict1.category != VerdictCategory.CONFIG

    # "room" should NOT match "oom"
    incident_room = _incident(
        title="Capacity warning",
        error_message="no room available in warehouse",
        stack_trace="",
        logs=["no room in storage rack 4"],
    )
    verdict2 = classify(incident_room, {}, "test")
    assert verdict2.category != VerdictCategory.RESOURCE


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


def test_mitigation_zero_error_rate_is_recovered(tmp_settings, monkeypatch: pytest.MonkeyPatch) -> None:
    service = MitigationService(tmp_settings)
    monkeypatch.setattr(service, "_error_rate", lambda: 0.0)
    monkeypatch.setattr(service, "_call", lambda action: None)
    monkeypatch.setattr(service, "_probe_error_rate", lambda: 0.0)
    incident = _incident(
        status="MITIGATION_PROPOSED",
        verdict=Verdict(
            category=VerdictCategory.RESOURCE,
            confidence=0.9,
            recommended_track=RecommendedTrack.MITIGATION,
            recommended_action="restart",
            provider="mock",
        ),
    )
    record = service.execute(incident, "tester")
    assert record.recovered is True
    assert record.error_rate_before == 0.0
    assert record.error_rate_after == 0.0


def test_diff_parser_handles_comment_removal() -> None:
    diff = (
        "--- a/test.sql\n"
        "+++ b/test.sql\n"
        "@@ -1,3 +1,2 @@\n"
        " select 1;\n"
        "--- old comment\n"
        " select 2;\n"
    )
    patches = parse_file_patches(diff)
    assert len(patches) == 1
    assert patches[0].path == "test.sql"
    assert len(patches[0].hunks) == 1
    assert "--- old comment" in patches[0].hunks[0]


def test_rejects_patching_protected_test_files(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "conftest.py").write_text("# config", encoding="utf-8")
    (workspace / "test_app.py").write_text("def test_ok(): assert True", encoding="utf-8")

    diff_conftest = (
        "--- a/conftest.py\n"
        "+++ b/conftest.py\n"
        "@@ -1,1 +1,1 @@\n"
        "-# config\n"
        "+# hacked\n"
    )
    with pytest.raises(SentinelAIError) as exc1:
        apply_unified_diff(diff_conftest, workspace)
    assert exc1.value.code == "protected_file_modified"

    diff_test = (
        "--- a/test_app.py\n"
        "+++ b/test_app.py\n"
        "@@ -1,1 +1,1 @@\n"
        "-def test_ok(): assert True\n"
        "+def test_ok(): assert False\n"
    )
    with pytest.raises(SentinelAIError) as exc2:
        apply_unified_diff(diff_test, workspace)
    assert exc2.value.code == "protected_file_modified"


def test_resolve_repository_path_blocks_root_and_traversal(tmp_settings) -> None:
    # Project root is rejected
    with pytest.raises(SentinelAIError) as exc_root:
        resolve_repository_path(".", tmp_settings)
    assert exc_root.value.code == "unsafe_path"

    # Sibling directory is rejected
    with pytest.raises(SentinelAIError) as exc_sibling:
        resolve_repository_path("victim_app-evil", tmp_settings)
    assert exc_sibling.value.code in {"disallowed_repository", "invalid_repository"}


@pytest.mark.anyio
async def test_event_hub_publish_sync_from_thread() -> None:
    import asyncio

    hub = EventHub()
    loop = asyncio.get_running_loop()
    hub.set_loop(loop)
    queue = await hub.subscribe()

    def _sender():
        hub.publish_sync({"type": "test_sync"})

    t = threading.Thread(target=_sender)
    t.start()
    t.join()

    msg = await asyncio.wait_for(queue.get(), timeout=2.0)
    assert "test_sync" in msg
    hub.unsubscribe(queue)


def test_authentication_enforcement_and_actor_derivation(tmp_settings) -> None:
    from fastapi.testclient import TestClient

    from backend.app.api.deps import build_container
    from backend.app.main import create_app

    auth_settings = replace(tmp_settings, auth_enabled=True, api_key="secret-key")
    container = build_container(auth_settings)
    app = create_app(auth_settings, container)
    auth_client = TestClient(app)

    # 1. Unauthenticated request to protected endpoint -> 401
    resp = auth_client.post("/api/alerts", json={"error_message": "test", "service": "checkout"})
    assert resp.status_code == 401

    # 2. Invalid API key -> 403
    resp = auth_client.post(
        "/api/alerts",
        json={"error_message": "test", "service": "checkout"},
        headers={"Authorization": "Bearer wrong-key"},
    )
    assert resp.status_code == 403

    # 3. Valid key with custom actor in token -> 201
    resp = auth_client.post(
        "/api/alerts",
        json={"error_message": "test", "service": "checkout"},
        headers={"Authorization": "Bearer secret-key:ops-lead"},
    )
    assert resp.status_code == 201
