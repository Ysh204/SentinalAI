"""Collect limited source context from an allowed repository path."""

from __future__ import annotations

from pathlib import Path

from backend.app.core.config import Settings
from backend.app.core.exceptions import SentinelAIError

MAX_FILES = 20
MAX_FILE_BYTES = 20_000
ALLOWED_SUFFIXES = {".py", ".txt", ".md", ".toml", ".json"}
DISALLOWED_NAMES = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", "data", "workspaces"}


def resolve_repository_path(raw: str | None, settings: Settings) -> Path:
    candidate = Path(raw) if raw else settings.sample_app_path
    if not candidate.is_absolute():
        candidate = settings.project_root / candidate
    resolved = candidate.resolve()
    root = settings.project_root.resolve()

    if resolved == root:
        raise SentinelAIError(
            "Project root cannot be used as an incident repository path.",
            code="unsafe_path",
            status_code=400,
        )

    try:
        is_rel = resolved.is_relative_to(root)
    except AttributeError:
        is_rel = str(resolved).startswith(str(root) + Path("/").name)

    if not is_rel:
        raise SentinelAIError(
            "repository_path must stay inside the SentinelAI project directory.",
            code="unsafe_path",
            status_code=400,
        )

    rel = resolved.relative_to(root)
    allowed = getattr(settings, "allowed_repositories", ("sample_app", "victim_app"))
    if not rel.parts or rel.parts[0] not in allowed:
        raise SentinelAIError(
            f"repository_path must be one of the allowed repositories: {', '.join(allowed)}.",
            code="disallowed_repository",
            status_code=400,
        )

    if not resolved.exists() or not resolved.is_dir():
        raise SentinelAIError(
            "repository_path does not exist or is not a directory.",
            code="invalid_repository",
            status_code=400,
        )
    return resolved


def collect_source_context(repo_path: Path) -> tuple[str, list[str]]:
    chunks: list[str] = []
    files: list[str] = []
    for path in sorted(repo_path.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in ALLOWED_SUFFIXES:
            continue
        if path.name.startswith(".env") or any(part.startswith(".") or part in DISALLOWED_NAMES for part in path.parts):
            continue
        if path.stat().st_size > MAX_FILE_BYTES:
            continue
        relative = str(path.relative_to(repo_path)).replace("\\", "/")
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        files.append(relative)
        chunks.append(f"--- {relative}\n{content}")
        if len(files) >= MAX_FILES:
            break
    return "\n\n".join(chunks), files
