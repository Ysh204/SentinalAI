"""Apply a patch only in a disposable workspace and run real tests."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from backend.app.core.config import Settings
from backend.app.core.exceptions import SentinelAIError
from backend.app.models.schemas import IncidentPublic, ValidationCheck, ValidationResults
from backend.app.services.diff_utils import apply_unified_diff
from backend.app.services.git_service import init_local_baseline
from backend.app.services.source_context import resolve_repository_path

DISCLAIMER = (
    "A passing test run does not guarantee the fix is correct, complete, or safe. "
    "This prototype never modifies the original repository."
)


class Validator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def validate(self, incident: IncidentPublic) -> ValidationResults:
        if not incident.proposed_patch:
            raise SentinelAIError(
                "Cannot validate without a proposed patch.",
                code="missing_patch",
                status_code=409,
            )
        repo = resolve_repository_path(incident.repository_path, self.settings)
        self.settings.workspace_root.mkdir(parents=True, exist_ok=True)
        workspace: Path | None = None
        try:
            workspace = Path(
                tempfile.mkdtemp(
                    prefix=f"incident-{incident.id[:8]}-",
                    dir=self.settings.workspace_root,
                )
            )
            _copy_tree(repo, workspace)
            try:
                init_local_baseline(workspace)
            except Exception:
                # Git init is optional for validation; tests still run.
                pass
            applied = apply_unified_diff(incident.proposed_patch, workspace)
            pytest_check = self._run_pytest(workspace)
            ruff_check = self._run_ruff(workspace)
            checks = [pytest_check, ruff_check]
            overall = pytest_check.status == "passed"
            return ValidationResults(
                overall_passed=overall,
                checks=checks,
                applied_files=applied,
                workspace=str(workspace.name),
                disclaimer=DISCLAIMER,
            )
        except SentinelAIError as exc:
            return ValidationResults(
                overall_passed=False,
                checks=[
                    ValidationCheck(
                        name="patch_apply",
                        status="failed",
                        detail=exc.message,
                    )
                ],
                applied_files=[],
                workspace=workspace.name if workspace else None,
                disclaimer=DISCLAIMER,
            )
        finally:
            if workspace and workspace.exists():
                shutil.rmtree(workspace, ignore_errors=True)

    def _run_pytest(self, workspace: Path) -> ValidationCheck:
        return self._run_check(
            name="pytest",
            command=[sys.executable, "-m", "pytest", "-q", "--tb=short"],
            cwd=workspace,
            timeout=self.settings.pytest_timeout,
        )

    def _run_ruff(self, workspace: Path) -> ValidationCheck:
        return self._run_check(
            name="ruff",
            command=[sys.executable, "-m", "ruff", "check", "."],
            cwd=workspace,
            timeout=self.settings.ruff_timeout,
        )

    def _run_check(
        self,
        name: str,
        command: list[str],
        cwd: Path,
        timeout: int,
    ) -> ValidationCheck:
        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                shell=False,
            )
        except FileNotFoundError:
            return ValidationCheck(name=name, status="skipped", detail=f"{name} is not installed.")
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            return ValidationCheck(
                name=name,
                status="failed",
                detail=f"{name} timed out after {timeout}s.",
                exit_code=None,
                stdout=stdout[-4000:],
                stderr=stderr[-4000:],
            )

        stdout = completed.stdout[-4000:]
        stderr = completed.stderr[-4000:]
        if name == "ruff" and completed.returncode == 1 and "No module named ruff" in (stderr + stdout):
            return ValidationCheck(name=name, status="skipped", detail="Ruff is not installed.")
        if completed.returncode == 0:
            status = "passed"
            detail = f"{name} passed."
        else:
            status = "failed"
            detail = f"{name} failed with exit code {completed.returncode}."
        return ValidationCheck(
            name=name,
            status=status,
            detail=detail,
            exit_code=completed.returncode,
            stdout=stdout,
            stderr=stderr,
        )


def _copy_tree(src: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        if item.name in {".git", "__pycache__", ".venv", ".pytest_cache", ".ruff_cache"}:
            continue
        target = dest / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)
