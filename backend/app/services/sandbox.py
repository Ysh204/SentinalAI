"""Restricted subprocess environment for untrusted patch/test execution."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

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


def run_sandboxed(
    command: Sequence[str],
    *,
    cwd: Path,
    timeout: int,
    extra_env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = sandbox_env(cwd)
    if extra_env:
        env.update(extra_env)
    kwargs: dict = {
        "cwd": cwd,
        "capture_output": True,
        "text": True,
        "timeout": timeout,
        "check": False,
        "shell": False,
        "env": env,
    }
    preexec = posix_rlimits()
    if preexec is not None:
        kwargs["preexec_fn"] = preexec
    return subprocess.run(list(command), **kwargs)


def current_interpreter() -> str:
    return sys.executable
