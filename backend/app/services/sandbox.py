"""Restricted subprocess environment for untrusted patch/test execution."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from backend.app.core.exceptions import SentinelAIError

LOGGER = logging.getLogger("sentinelai.sandbox")
_WARNED_UNISOLATED = False

# Host secrets (API keys, cloud creds) must never enter the sandbox.
_ALLOWED_ENV = (
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "SYSTEMDRIVE",
    "WINDIR",
    "COMSPEC",
    "TEMP",
    "TMP",
    "TMPDIR",
    "HOME",
    "USERPROFILE",
    "HOMEDRIVE",
    "HOMEPATH",
    "PROGRAMFILES",
    "PROGRAMFILES(X86)",
    "PROGRAMDATA",
    "LOCALAPPDATA",
    "LANG",
    "LC_ALL",
    "PYTHONIOENCODING",
    "PYTHONDONTWRITEBYTECODE",
    "NUMBER_OF_PROCESSORS",
    "PROCESSOR_ARCHITECTURE",
)


def sandbox_env(pythonpath: str | os.PathLike[str]) -> dict[str, str]:
    env: dict[str, str] = {}
    for key in _ALLOWED_ENV:
        value = os.environ.get(key)
        if value:
            env[key] = value
    env["PYTHONPATH"] = str(pythonpath)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONSAFEPATH"] = "1"
    env["PYTHONUTF8"] = "1"
    # Null route proxies to block outbound HTTP/HTTPS calls from untrusted patch code
    env["http_proxy"] = "http://127.0.0.1:0"
    env["https_proxy"] = "http://127.0.0.1:0"
    env["all_proxy"] = "socks5://127.0.0.1:0"
    return env


def posix_rlimits():
    """Return a preexec_fn that caps CPU and address space, or None on Windows."""
    if os.name == "nt":
        return None
    try:
        import resource
    except ImportError:
        return None

    def _limit() -> None:
        cpu = (15, 15)
        mem = (512 * 1024 * 1024, 512 * 1024 * 1024)
        try:
            resource.setrlimit(resource.RLIMIT_CPU, cpu)
        except (ValueError, OSError):
            pass
        try:
            resource.setrlimit(resource.RLIMIT_AS, mem)
        except (ValueError, OSError):
            pass
        try:
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        except (ValueError, OSError):
            pass

    return _limit


def docker_command(
    command: Sequence[str],
    *,
    cwd: Path,
    image: str,
    name: str,
) -> list[str]:
    """Build a `docker run` invocation with no network, a read-only root fs and capped resources."""
    args = [
        "docker", "run", "--rm", "--name", name,
        "--network", "none",
        "--read-only",
        "--tmpfs", "/tmp:rw,nosuid,size=64m",  # noqa: S108 - container-local scratch space
        "--memory", "512m", "--memory-swap", "512m", "--cpus", "1", "--pids-limit", "128",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
    ]
    if hasattr(os, "getuid"):
        # Same uid as the host owner so the bind-mounted workspace is readable; still unprivileged.
        args += ["--user", f"{os.getuid()}:{os.getgid()}"]
    args += [
        "-e", "PYTHONDONTWRITEBYTECODE=1",
        "-e", "PYTHONPATH=/work",
        "-e", "PYTHONSAFEPATH=1",
        "-e", "PYTHONUTF8=1",
        "-e", "HOME=/tmp",
        "-e", "RUFF_CACHE_DIR=/tmp/ruff",
        "-e", "PYTEST_ADDOPTS=-p no:cacheprovider",
        "-v", f"{cwd}:/work:rw",
        "-w", "/work",
        image,
    ]
    inner = ["python" if part == sys.executable else part for part in command]
    return args + inner


def _run_docker(command: Sequence[str], *, cwd: Path, timeout: int, image: str) -> subprocess.CompletedProcess[str]:
    if shutil.which("docker") is None:
        raise SentinelAIError(
            "SANDBOX_MODE=docker but the docker CLI was not found. Refusing to run untrusted code on the host.",
            code="sandbox_unavailable",
            status_code=503,
        )
    name = f"sentinel-{uuid.uuid4().hex[:12]}"
    argv = docker_command(command, cwd=cwd, image=image, name=name)
    try:
        completed = subprocess.run(  # noqa: S603
            argv, capture_output=True, text=True, timeout=timeout, check=False, shell=False
        )
    except subprocess.TimeoutExpired:
        # Killing the CLI does not stop the container, so stop it explicitly.
        subprocess.run(["docker", "kill", name], capture_output=True, check=False, timeout=15)  # noqa: S603, S607
        raise
    if completed.returncode == 125:  # docker itself failed (image missing, daemon down, bad flag)
        raise SentinelAIError(
            f"Docker could not start the sandbox: {(completed.stderr or '').strip()[-300:]}",
            code="sandbox_unavailable",
            status_code=503,
        )
    return completed


def _kill_process_tree(proc: subprocess.Popen) -> None:
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
                check=False,
                timeout=5,
            )
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    else:
        import signal

        try:
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, signal.SIGKILL)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def run_sandboxed(
    command: Sequence[str],
    *,
    cwd: Path,
    timeout: int,
    extra_env: Mapping[str, str] | None = None,
    settings=None,
) -> subprocess.CompletedProcess[str]:
    global _WARNED_UNISOLATED
    if settings is not None and getattr(settings, "sandbox_mode", "subprocess") == "docker":
        return _run_docker(command, cwd=cwd, timeout=timeout, image=settings.sandbox_image)
    if not _WARNED_UNISOLATED:
        _WARNED_UNISOLATED = True
        LOGGER.warning("Running patch tests in a plain subprocess (no network or filesystem isolation).")
    env = sandbox_env(cwd)
    if extra_env:
        env.update(extra_env)

    extra_flags: dict[str, Any] = {}
    if os.name == "nt":
        extra_flags["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        extra_flags["start_new_session"] = True

    proc = subprocess.Popen(
        list(command),
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        **extra_flags,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        _kill_process_tree(proc)
        try:
            out, err = proc.communicate(timeout=2)
        except Exception:
            out, err = "", ""
        raise subprocess.TimeoutExpired(
            cmd=list(command),
            timeout=timeout,
            output=out or exc.stdout or "",
            stderr=err or exc.stderr or "",
        ) from None
    except Exception:
        _kill_process_tree(proc)
        raise

    return subprocess.CompletedProcess(
        args=list(command),
        returncode=proc.returncode if proc.returncode is not None else -1,
        stdout=stdout,
        stderr=stderr,
    )


def current_interpreter() -> str:
    return sys.executable
