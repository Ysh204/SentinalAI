"""Application settings loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_CORS_ORIGINS = (
    "http://localhost:8501",
    "http://127.0.0.1:8501",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5175",
)


def _parse_api_keys(raw: str | None) -> tuple[tuple[str, str], ...]:
    """Parse ``API_KEYS="alice=tok1,bob=tok2"`` into ((token, actor), ...). Bad input fails closed."""
    pairs: list[tuple[str, str]] = []
    for chunk in (raw or "").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        name, sep, token = chunk.partition("=")
        name, token = name.strip(), token.strip()
        if not sep or not name or not token:
            raise ValueError("API_KEYS entries must look like name=token (comma separated).")
        if name.lower() == "anonymous":
            raise ValueError("'anonymous' is reserved and cannot be used as an API key identity.")
        pairs.append((token, name))
    return tuple(pairs)


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else default


def _as_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_version: str
    team_name: str
    ai_provider: str
    gemini_api_key: str | None
    gemini_model: str
    database_path: Path
    workspace_root: Path
    sample_app_path: Path
    project_root: Path
    backend_url: str
    victim_app_url: str
    pytest_timeout: int
    ruff_timeout: int
    log_level: str
    health_watcher_enabled: bool
    health_check_interval: float
    health_fail_threshold: int
    api_key: str | None = None
    auth_enabled: bool = False
    cors_origins: tuple[str, ...] = DEFAULT_CORS_ORIGINS
    allowed_repositories: tuple[str, ...] = ("sample_app", "victim_app")
    api_keys: tuple[tuple[str, str], ...] = ()  # (token, actor) pairs
    demo_mode: bool = True
    sandbox_mode: str = "subprocess"  # "subprocess" (dev only) or "docker"
    sandbox_image: str = "sentinelai-sandbox:latest"
    stuck_timeout_seconds: int = 300

    @property
    def credentials(self) -> tuple[tuple[str, str], ...]:
        """All accepted (token, actor) pairs. The legacy single key maps to a fixed identity."""
        keys = list(self.api_keys)
        if self.api_key:
            keys.append((self.api_key, "authenticated-user"))
        return tuple(keys)

    @property
    def gemini_configured(self) -> bool:
        return bool(self.gemini_api_key)


def load_settings() -> Settings:
    database_path = _as_path(_env("DATABASE_PATH", "data/sentinelai.db") or "data/sentinelai.db")
    workspace_root = _as_path(_env("WORKSPACE_ROOT", "data/workspaces") or "data/workspaces")
    api_key = _env("SENTINEL_API_KEY") or _env("API_KEY")
    api_keys = _parse_api_keys(_env("API_KEYS"))
    auth_env = _env("AUTH_ENABLED")
    auth_enabled = (auth_env.lower() in {"1", "true", "yes"}) if auth_env else bool(api_key or api_keys)
    sandbox_mode = (_env("SANDBOX_MODE", "subprocess") or "subprocess").lower()
    if sandbox_mode not in {"subprocess", "docker"}:
        raise ValueError("SANDBOX_MODE must be 'subprocess' or 'docker'.")
    cors_raw = _env("CORS_ORIGINS")
    cors_origins = (
        tuple(origin.strip() for origin in cors_raw.split(",") if origin.strip())
        if cors_raw
        else DEFAULT_CORS_ORIGINS
    )
    return Settings(
        app_name="SentinelAI",
        app_version="0.1.0",
        team_name="Team TriNova",
        ai_provider=(_env("AI_PROVIDER", "mock") or "mock").lower(),
        gemini_api_key=_env("GEMINI_API_KEY"),
        gemini_model=_env("GEMINI_MODEL", "gemini-2.0-flash") or "gemini-2.0-flash",
        database_path=database_path,
        workspace_root=workspace_root,
        sample_app_path=PROJECT_ROOT / "sample_app",
        project_root=PROJECT_ROOT,
        backend_url=_env("BACKEND_URL", "http://127.0.0.1:8000") or "http://127.0.0.1:8000",
        victim_app_url=_env("VICTIM_APP_URL", "http://127.0.0.1:8001") or "http://127.0.0.1:8001",
        pytest_timeout=int(_env("PYTEST_TIMEOUT", "30") or "30"),
        ruff_timeout=int(_env("RUFF_TIMEOUT", "20") or "20"),
        log_level=(_env("LOG_LEVEL", "INFO") or "INFO").upper(),
        health_watcher_enabled=(_env("HEALTH_WATCHER_ENABLED", "true") or "true").lower()
        in {"1", "true", "yes"},
        health_check_interval=float(_env("HEALTH_CHECK_INTERVAL", "10") or "10"),
        health_fail_threshold=int(_env("HEALTH_FAIL_THRESHOLD", "3") or "3"),
        api_key=api_key,
        auth_enabled=auth_enabled,
        cors_origins=cors_origins,
        allowed_repositories=("sample_app", "victim_app"),
        api_keys=api_keys,
        demo_mode=(_env("DEMO_MODE", "true") or "true").lower() in {"1", "true", "yes"},
        sandbox_mode=sandbox_mode,
        sandbox_image=_env("SANDBOX_IMAGE", "sentinelai-sandbox:latest") or "sentinelai-sandbox:latest",
        stuck_timeout_seconds=int(_env("STUCK_TIMEOUT_SECONDS", "300") or "300"),
    )


settings = load_settings()
