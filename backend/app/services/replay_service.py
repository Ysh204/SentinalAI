"""Replay a captured failing request against a patched sandbox copy."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from backend.app.core.config import Settings
from backend.app.core.exceptions import SentinelAIError
from backend.app.models.schemas import IncidentPublic, ReplayResult, ValidationCheck
from backend.app.services.diff_utils import apply_unified_diff
from backend.app.services.source_context import resolve_repository_path
from backend.app.services.validator import Validator, _copy_tree

REPRO_TEST = '''
from shop import _line_total

def test_line_total_none_is_zero():
    assert _line_total(None) == 0
    assert _line_total({"price": 2, "qty": 3}) == 6
'''


class ReplayService:
    def __init__(self, settings: Settings, validator: Validator) -> None:
        self.settings = settings
        self.validator = validator

    def replay(self, incident: IncidentPublic) -> ReplayResult:
        if not incident.proposed_patch:
            raise SentinelAIError("A patch is required before replay.", code="missing_patch", status_code=409)
        captured = incident.captured_request or {}
        before_status = None
        if isinstance(captured, dict):
            before_status = captured.get("status_code")
        if before_status is None:
            before_status = 500
        before_ok = int(before_status) < 400

        repo = resolve_repository_path(incident.repository_path, self.settings)
        self.settings.workspace_root.mkdir(parents=True, exist_ok=True)
        workspace: Path | None = None
        try:
            workspace = Path(
                tempfile.mkdtemp(
                    prefix=f"replay-{incident.id[:8]}-",
                    dir=self.settings.workspace_root,
                )
            )
            _copy_tree(repo, workspace)
            apply_unified_diff(incident.proposed_patch, workspace)
            (workspace / "test_repro_checkout.py").write_text(REPRO_TEST, encoding="utf-8")
            after_ok, detail = self._run_repro(workspace)
            return ReplayResult(
                before_status=int(before_status),
                after_status=200 if after_ok else 500,
                before_ok=before_ok,
                after_ok=after_ok,
                request_path=str(captured.get("path") or "/checkout"),
                detail=detail,
                sandbox=workspace.name,
            )
        finally:
            if workspace and workspace.exists():
                shutil.rmtree(workspace, ignore_errors=True)

    def _run_repro(self, workspace: Path) -> tuple[bool, str]:
        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = str(workspace)
            completed = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "test_repro_checkout.py", "--tb=short"],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=self.settings.pytest_timeout,
                check=False,
                shell=False,
                env=env,
            )
        except subprocess.TimeoutExpired:
            return False, "Replay tests timed out."
        stdout = (completed.stdout or "")[-2000:]
        stderr = (completed.stderr or "")[-2000:]
        ok = completed.returncode == 0
        return ok, f"exit={completed.returncode}\n{stdout}\n{stderr}"


def as_check(replay: ReplayResult) -> ValidationCheck:
    return ValidationCheck(
        name="request_replay",
        status="passed" if replay.after_ok and not replay.before_ok else ("passed" if replay.after_ok else "failed"),
        detail=f"before={'ok' if replay.before_ok else 'fail'} after={'ok' if replay.after_ok else 'fail'}. {replay.detail}",
    )
