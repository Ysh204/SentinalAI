"""Apply a patch only in a disposable workspace and run real tests."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from backend.app.core.config import Settings
from backend.app.core.exceptions import SentinelAIError
from backend.app.models.schemas import IncidentPublic, ValidationCheck, ValidationResults
from backend.app.services.diff_utils import apply_unified_diff
from backend.app.services.git_service import init_local_baseline
from backend.app.services.sandbox import current_interpreter, run_sandboxed
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
            # Copy regression test fixtures into test files for validation
            fixtures_dir = workspace / "fixtures"
            if fixtures_dir.is_dir():
                for fixture in fixtures_dir.glob("regression_*.py"):
                    shutil.copy2(fixture, workspace / f"test_{fixture.name}")

            try:
                init_local_baseline(workspace)
            except Exception:
                # Git init is optional for validation; tests still run.
                pass
            baseline_check = self._run_check(
                name="baseline_pytest",
                command=[current_interpreter(), "-m", "pytest", "-q", "--tb=short"],
                cwd=workspace,
                timeout=self.settings.pytest_timeout,
            )
            failed_tests = re.findall(r"FAILED\s+(\S+)", baseline_check.stdout or "")

            applied = apply_unified_diff(incident.proposed_patch, workspace)
            pytest_check = self._run_pytest(workspace)
            ruff_check = self._run_ruff(workspace)
            checks = [baseline_check, pytest_check, ruff_check]
            overall = (
                baseline_check.status == "failed"
                and baseline_check.exit_code == 1
                and pytest_check.status == "passed"
                and pytest_check.exit_code == 0
                and ruff_check.status in {"passed", "skipped"}
            )
            if overall and failed_tests:
                baseline_check.detail = (
                    f"Baseline reproduced failure in {', '.join(failed_tests)}; patch resolved it."
                )
            elif baseline_check.exit_code == 0:
                baseline_check.detail = "Baseline pytest passed without patch; bug was not reproduced."
            elif baseline_check.exit_code is not None and baseline_check.exit_code != 1:
                baseline_check.detail = (
                    f"Baseline pytest exited with code {baseline_check.exit_code} "
                    "(syntax or collection error, not an assertion failure)."
                )
            return ValidationResults(
                overall_passed=overall,
                checks=checks,
                applied_files=applied,
                workspace=str(workspace.name),
                disclaimer=DISCLAIMER,
            )
        except SentinelAIError as exc:
            if exc.code == "sandbox_unavailable" or exc.status_code >= 500:
                raise
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
            command=[current_interpreter(), "-m", "pytest", "-q", "--tb=short"],
            cwd=workspace,
            timeout=self.settings.pytest_timeout,
        )

    def _run_ruff(self, workspace: Path) -> ValidationCheck:
        return self._run_check(
            name="ruff",
            command=[current_interpreter(), "-m", "ruff", "check", ".", "--ignore", "N999"],
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
            completed = run_sandboxed(command, cwd=cwd, timeout=timeout, settings=self.settings)
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
        except SentinelAIError:
            raise
        except Exception as exc:
            return ValidationCheck(
                name=name,
                status="failed",
                detail=f"{name} process raised an error: {exc}",
                exit_code=-1,
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
        if item.name.startswith(".env"):
            continue
        if item.name in {".git", "__pycache__", ".venv", ".pytest_cache", ".ruff_cache", "data", "workspaces"}:
            continue
        target = dest / item.name
        if item.is_dir():
            shutil.copytree(
                item,
                target,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(".env*", "*.pyc", "__pycache__"),
            )
        else:
            shutil.copy2(item, target)
