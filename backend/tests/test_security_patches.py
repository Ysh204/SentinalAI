"""Regression tests for the hardening patches (auth, sandbox, regressions, pagination, probes)."""

from __future__ import annotations

import sqlite3
import subprocess
import threading
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.api.deps import build_container
from backend.app.core.config import load_settings
from backend.app.core.exceptions import SentinelAIError
from backend.app.db.database import Database
from backend.app.main import create_app
from backend.app.models.incident import IncidentStatus
from backend.app.models.schemas import IncidentCreate
from backend.app.repositories.incident_repository import IncidentRepository
from backend.app.services import sandbox
from backend.app.services.mitigation import MitigationService
from backend.app.services.validator import Validator

OPEN_PATHS = {"/health", "/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"}
KEYS = (("tok-alice", "alice"), ("tok-bob", "bob"))


def _client(settings, **overrides) -> TestClient:
    s = replace(settings, **overrides)
    return TestClient(create_app(s, build_container(s)))


# --------------------------------------------------------------------------- auth
def test_every_route_except_health_requires_credentials(tmp_settings) -> None:
    client = _client(tmp_settings, auth_enabled=True, api_keys=KEYS)
    # Enumerate through OpenAPI: app.routes does not expose included routers in newer FastAPI versions.
    checked = 0
    for route_path, operations in client.app.openapi()["paths"].items():
        if route_path in OPEN_PATHS:
            continue
        path = route_path.replace("{incident_id}", "x")
        for method in operations:
            resp = client.request(method.upper(), path)
            assert resp.status_code == 401, f"{method.upper()} {route_path} -> {resp.status_code} without credentials"
            checked += 1
    assert checked >= 15  # guards against the loop silently checking nothing
    assert client.get("/health").status_code == 200


def test_auth_enabled_without_keys_refuses_to_start(tmp_settings) -> None:
    with pytest.raises(RuntimeError):
        create_app(replace(tmp_settings, auth_enabled=True, api_keys=(), api_key=None))


def test_actor_comes_from_the_key_not_the_request(tmp_settings) -> None:
    client = _client(tmp_settings, auth_enabled=True, api_keys=KEYS)
    created = client.post("/api/demo/simulate", headers={"Authorization": "Bearer tok-alice"})
    assert created.status_code == 200
    incident_id = created.json()["id"]
    resp = client.post(
        f"/api/incidents/{incident_id}/approve",
        json={"actor": "mallory"},  # must be ignored
        headers={"X-API-Key": "tok-bob"},
    )
    assert resp.status_code == 200
    assert resp.json()["approval"]["actor"] == "bob"


def test_old_key_colon_actor_trick_is_rejected(tmp_settings) -> None:
    client = _client(tmp_settings, auth_enabled=True, api_keys=KEYS)
    resp = client.get("/api/incidents", headers={"Authorization": "Bearer tok-alice:CEO"})
    assert resp.status_code == 403


def test_event_stream_requires_a_token(tmp_settings) -> None:
    client = _client(tmp_settings, auth_enabled=True, api_keys=KEYS)
    assert client.get("/api/events").status_code == 401
    assert client.get("/api/events?access_token=wrong").status_code == 403


def test_demo_endpoints_can_be_disabled(tmp_settings) -> None:
    client = _client(tmp_settings, demo_mode=False)
    assert client.post("/api/demo/simulate").status_code == 404
    assert client.post("/api/eval/run").status_code == 404


def test_settings_parse_named_keys_and_reject_bad_config(monkeypatch) -> None:
    monkeypatch.setenv("API_KEYS", "alice=t1, bob=t2")
    settings = load_settings()
    assert settings.auth_enabled is True
    assert dict(settings.credentials) == {"t1": "alice", "t2": "bob"}
    for bad in ("justatoken", "=t1", "anonymous=t1"):
        monkeypatch.setenv("API_KEYS", bad)
        with pytest.raises(ValueError):
            load_settings()
    monkeypatch.setenv("API_KEYS", "")
    monkeypatch.setenv("SANDBOX_MODE", "chroot")
    with pytest.raises(ValueError):
        load_settings()


# --------------------------------------------------------------------------- regressions
def test_validator_reports_timeout_with_partial_output(tmp_settings, monkeypatch) -> None:
    def boom(*_a, **_k):
        raise subprocess.TimeoutExpired(cmd="pytest", timeout=1, output=b"partial", stderr=b"slow")

    monkeypatch.setattr("backend.app.services.validator.run_sandboxed", boom)
    check = Validator(tmp_settings)._run_check("pytest", ["pytest"], Path("."), 1)
    assert check.status == "failed" and "timed out" in check.detail
    assert check.stdout == "partial" and check.stderr == "slow"


def test_validator_marks_missing_tool_as_skipped(tmp_settings, monkeypatch) -> None:
    def missing(*_a, **_k):
        raise FileNotFoundError("ruff")

    monkeypatch.setattr("backend.app.services.validator.run_sandboxed", missing)
    assert Validator(tmp_settings)._run_check("ruff", ["ruff"], Path("."), 1).status == "skipped"


def test_validator_propagates_sandbox_unavailable(tmp_settings, monkeypatch) -> None:
    def unavailable(*_a, **_k):
        raise SentinelAIError("no docker", code="sandbox_unavailable", status_code=503)

    monkeypatch.setattr("backend.app.services.validator.run_sandboxed", unavailable)
    with pytest.raises(SentinelAIError):
        Validator(tmp_settings)._run_check("pytest", ["pytest"], Path("."), 1)


def test_mitigation_fails_when_control_endpoint_errors(tmp_settings, monkeypatch) -> None:
    service = MitigationService(replace(tmp_settings, victim_app_url="http://shop.invalid"))
    monkeypatch.setattr(httpx, "post", lambda *a, **k: httpx.Response(500))
    with pytest.raises(SentinelAIError) as exc:
        service._call("rollback")
    assert exc.value.code == "mitigation_failed"


# --------------------------------------------------------------------------- pagination / recovery / migration
def _make_incidents(container, count: int) -> list[str]:
    ids = []
    for n in range(count):
        item = container.incidents.create(
            IncidentCreate(title=f"t{n}", error_message="e", repository_path="sample_app")
        )
        ids.append(item.id)
    return ids


def test_metrics_and_listing_do_not_truncate_at_one_page(tmp_settings) -> None:
    container = build_container(tmp_settings)
    _make_incidents(container, 105)
    client = TestClient(create_app(tmp_settings, container))
    assert client.get("/api/metrics").json()["incidents_total"] == 105
    assert len(client.get("/api/incidents").json()) == 100
    assert len(client.get("/api/incidents?limit=500").json()) == 105


def _age(container, incident_id: str, seconds: int) -> None:
    old = (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()
    conn = sqlite3.connect(container.database.path)
    conn.execute("UPDATE incidents SET updated_at = ? WHERE id = ?", (old, incident_id))
    conn.commit()
    conn.close()


def test_stuck_recovery_respects_age_and_live_locks(tmp_settings) -> None:
    container = build_container(tmp_settings)
    ids = _make_incidents(container, 3)
    for incident_id in ids:
        incident = container.incidents.get(incident_id)
        container.incidents.transition(incident, IncidentStatus.VALIDATING, "validate_started")
    fresh, stale, live = ids
    _age(container, stale, 3600)
    _age(container, live, 3600)

    orchestrator = container.orchestrator
    held = threading.Event()
    release = threading.Event()

    def hold_lock():
        with orchestrator._locks[live]:
            held.set()
            release.wait(5)

    worker = threading.Thread(target=hold_lock)
    worker.start()
    held.wait(5)
    try:
        recovered = orchestrator.recover_stuck_incidents(max_age_seconds=300)
    finally:
        release.set()
        worker.join()

    assert recovered == [stale]
    assert container.incidents.get(stale).status == IncidentStatus.FAILED
    assert container.incidents.get(fresh).status == IncidentStatus.VALIDATING  # too recent
    assert container.incidents.get(live).status == IncidentStatus.VALIDATING  # owned by a live worker


def test_old_databases_get_fingerprints_backfilled(tmp_path: Path) -> None:
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE incidents (id TEXT PRIMARY KEY, title TEXT NOT NULL, error_message TEXT NOT NULL,
        stack_trace TEXT NOT NULL, repository_path TEXT, status TEXT NOT NULL, root_cause_analysis TEXT,
        proposed_patch TEXT, validation_results TEXT, approval TEXT, history TEXT NOT NULL DEFAULT '[]',
        details TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"""
    )
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO incidents (id,title,error_message,stack_trace,repository_path,status,details,"
        "created_at,updated_at)"
        " VALUES ('a','t','e','', 'victim_app','TRIAGED','{\"fingerprint\": \"fp-old\"}',?,?)",
        (now, now),
    )
    conn.commit()
    conn.close()
    repo = IncidentRepository(Database(path))
    found = repo.find_open_by_fingerprint("fp-old")
    assert found is not None and found.id == "a"


# --------------------------------------------------------------------------- synthetic probe
def test_synthetic_probe_runs_the_path_without_side_effects(monkeypatch) -> None:
    from victim_app import shop, state
    from victim_app.main import app as shop_app

    def forbidden(**_kw):
        raise AssertionError("probe must not report incidents")

    monkeypatch.setattr(shop, "report_error", forbidden)
    state.inject("none")
    client = TestClient(shop_app)
    before = state.snapshot()
    resp = client.post("/checkout", headers={"X-Synthetic-Probe": "1"}, json={})
    assert resp.status_code == 200 and resp.json()["charge"]["status"] == "dry_run"
    after = state.snapshot()
    assert (after["ok_count"], after["error_count"], after["logs"]) == (
        before["ok_count"], before["error_count"], before["logs"],
    )

    state.inject("payments_outage")  # the probe must still see real failure modes
    try:
        assert client.post("/checkout", headers={"X-Synthetic-Probe": "1"}, json={}).status_code == 503
    finally:
        state.inject("none")


# --------------------------------------------------------------------------- docker sandbox
def test_docker_command_is_locked_down(tmp_path: Path) -> None:
    argv = sandbox.docker_command(
        [sandbox.current_interpreter(), "-m", "pytest"], cwd=tmp_path, image="img:1", name="n1"
    )
    joined = " ".join(argv)
    for flag in ("--network none", "--read-only", "--cap-drop ALL", "--pids-limit 128", "no-new-privileges"):
        assert flag in joined
    assert f"{tmp_path}:/work:rw" in argv
    assert argv[-3:] == ["python", "-m", "pytest"]  # host interpreter path never enters the container
    assert "SECRET" not in joined and "GEMINI" not in joined


def _docker_settings(tmp_settings):
    return replace(tmp_settings, sandbox_mode="docker")


def test_docker_mode_fails_closed_without_docker(tmp_settings, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(sandbox.shutil, "which", lambda _name: None)
    with pytest.raises(SentinelAIError) as exc:
        sandbox.run_sandboxed(["python", "-V"], cwd=tmp_path, timeout=5, settings=_docker_settings(tmp_settings))
    assert exc.value.code == "sandbox_unavailable"


def test_docker_mode_never_falls_back_to_host(tmp_settings, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(sandbox.shutil, "which", lambda _name: "/usr/bin/docker")
    calls: list[list[str]] = []

    def fake_run(argv, **_kw):
        calls.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, "ok", "")

    monkeypatch.setattr(sandbox.subprocess, "run", fake_run)
    result = sandbox.run_sandboxed(["python", "-V"], cwd=tmp_path, timeout=5, settings=_docker_settings(tmp_settings))
    assert result.stdout == "ok"
    assert len(calls) == 1 and calls[0][:2] == ["docker", "run"]


def test_docker_timeout_kills_the_container(tmp_settings, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(sandbox.shutil, "which", lambda _name: "/usr/bin/docker")
    calls: list[list[str]] = []

    def fake_run(argv, **_kw):
        calls.append(list(argv))
        if argv[1] == "run":
            raise subprocess.TimeoutExpired(argv, 1)
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(sandbox.subprocess, "run", fake_run)
    with pytest.raises(subprocess.TimeoutExpired):
        sandbox.run_sandboxed(["python", "-V"], cwd=tmp_path, timeout=1, settings=_docker_settings(tmp_settings))
    assert calls[-1][:2] == ["docker", "kill"] and calls[-1][2] == calls[0][calls[0].index("--name") + 1]


def test_docker_startup_failure_is_reported_as_unavailable(tmp_settings, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(sandbox.shutil, "which", lambda _name: "/usr/bin/docker")
    monkeypatch.setattr(
        sandbox.subprocess, "run", lambda argv, **_k: subprocess.CompletedProcess(argv, 125, "", "Unable to find image")
    )
    with pytest.raises(SentinelAIError) as exc:
        sandbox.run_sandboxed(["python", "-V"], cwd=tmp_path, timeout=1, settings=_docker_settings(tmp_settings))
    assert exc.value.code == "sandbox_unavailable" and "Unable to find image" in exc.value.message


def test_replay_worker_is_copied_into_the_workspace() -> None:
    from backend.app.services.replay_service import WORKER

    assert WORKER.exists()
