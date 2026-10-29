"""Replay a captured HTTP request against unpatched vs patched shop copies."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

import httpx

from backend.app.core.config import Settings
from backend.app.core.exceptions import SentinelAIError
from backend.app.models.schemas import IncidentPublic, ReplayResult, ValidationCheck
from backend.app.services.diff_utils import apply_unified_diff
from backend.app.services.sandbox import current_interpreter, run_sandboxed
from backend.app.services.source_context import resolve_repository_path
from backend.app.services.validator import _copy_tree

WORKER = Path(__file__).with_name("replay_worker.py")
DEFAULT_BODY = {
    "order_id": "ord-1001",
    "email": "customer@example.com",
    "card_number": "4242424242424242",
    "items": [{"sku": "mug", "price": 12, "qty": 1}],
}


class ReplayService:
    def __init__(self, settings: Settings, validator: Any = None) -> None:
        self.settings = settings
        self.validator = validator

    def replay(self, incident: IncidentPublic) -> ReplayResult:
        if not incident.proposed_patch:
            raise SentinelAIError("A patch is required before replay.", code="missing_patch", status_code=409)
        captured = incident.captured_request if isinstance(incident.captured_request, dict) else {}
        method = str(captured.get("method") or "POST")
        path = str(captured.get("path") or "/checkout")
        if not path.startswith("/"):
            path = "/checkout"
        body = captured.get("body") if isinstance(captured.get("body"), dict) else dict(DEFAULT_BODY)
        inject = _live_inject_mode(self.settings) or captured.get("inject")

        before_status, before_detail = self._dispatch_unpatched(method, path, body, inject)
        after_status, after_detail, sandbox_name = self._dispatch_patched(
            incident, method, path, body, inject
        )
        return ReplayResult(
            before_status=before_status,
            after_status=after_status,
            before_ok=before_status < 400,
            after_ok=after_status < 400,
            request_path=path,
            detail=(
                f"HTTP {method} {path} payload replayed. "
                f"unpatched={before_status} patched={after_status}. "
                f"inject={inject or 'none'}. {before_detail} | {after_detail}"
            ),
            sandbox=sandbox_name,
        )

    def _dispatch_unpatched(
        self, method: str, path: str, body: dict[str, Any], inject: str | None
    ) -> tuple[int, str]:
        url = self.settings.victim_app_url.rstrip("/")
        if url != "inline":
            try:
                response = httpx.request(
                    method,
                    f"{url}{path}",
                    json=body,
                    timeout=httpx.Timeout(3.0, connect=0.4),
                )
            except httpx.HTTPError as exc:
                raise SentinelAIError(
                    f"Victim app is unreachable at {url}; cannot replay the captured request.",
                    code="victim_unreachable",
                    status_code=503,
                ) from exc
            return int(response.status_code), f"live unpatched HTTP {response.status_code}"
        repo = resolve_repository_path("victim_app", self.settings)
        return self._run_sandbox_request(repo, method, path, body, inject, apply_patch=None)

    def _dispatch_patched(
        self,
        incident: IncidentPublic,
        method: str,
        path: str,
        body: dict[str, Any],
        inject: str | None,
    ) -> tuple[int, str, str]:
        repo = resolve_repository_path(incident.repository_path, self.settings)
        status, detail = self._run_sandbox_request(
            repo, method, path, body, inject, apply_patch=incident.proposed_patch
        )
        return status, detail, "patched-sandbox"

    def _run_sandbox_request(
        self,
        repo: Path,
        method: str,
        path: str,
        body: dict[str, Any],
        inject: str | None,
        apply_patch: str | None,
    ) -> tuple[int, str]:
        self.settings.workspace_root.mkdir(parents=True, exist_ok=True)
        workspace: Path | None = None
        try:
            workspace = Path(
                tempfile.mkdtemp(prefix="replay-http-", dir=self.settings.workspace_root)
            )
            _copy_tree(repo, workspace)
            label = "unpatched"
            if apply_patch:
                apply_unified_diff(apply_patch, workspace)
                label = "patched"
            spec = {
                "method": method,
                "path": path,
                "json": body,
                "inject": inject,
            }
            spec_path = workspace / "_replay_request.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            worker_path = workspace / "_replay_worker.py"
            shutil.copy2(WORKER, worker_path)  # inside the workspace so a container can see it
            completed = run_sandboxed(
                [current_interpreter(), worker_path.name, spec_path.name],
                cwd=workspace,
                timeout=self.settings.pytest_timeout,
                settings=self.settings,
            )
            stdout = (completed.stdout or "").strip()
            stderr = (completed.stderr or "")[-1500:]
            if completed.returncode != 0:
                return 500, f"{label} worker exit={completed.returncode} {stderr}"
            try:
                payload = json.loads(stdout)
            except json.JSONDecodeError:
                return 500, f"{label} worker returned non-JSON: {stdout[:500]}"
            status = int(payload.get("status_code") or 500)
            return status, f"{label} sandbox HTTP {status}"
        finally:
            if workspace and workspace.exists():
                shutil.rmtree(workspace, ignore_errors=True)


def _live_inject_mode(settings: Settings) -> str | None:
    url = settings.victim_app_url.rstrip("/")
    if url == "inline":
        from victim_app import state

        mode = str(state.snapshot().get("failure_mode") or "")
        return mode if mode and mode != "none" else None
    try:
        response = httpx.get(f"{url}/control/context", timeout=httpx.Timeout(1.5, connect=0.2))
    except httpx.HTTPError:
        return None
    if response.status_code != 200:
        return None
    mode = str(response.json().get("failure_mode") or "")
    return mode if mode and mode != "none" else None


def as_check(replay: ReplayResult) -> ValidationCheck:
    status = (
        "passed"
        if replay.after_ok and not replay.before_ok
        else ("passed" if replay.after_ok else "failed")
    )
    before_status = "ok" if replay.before_ok else "fail"
    after_status = "ok" if replay.after_ok else "fail"
    return ValidationCheck(
        name="request_replay",
        status=status,
        detail=f"before={before_status} after={after_status}. {replay.detail}",
    )
