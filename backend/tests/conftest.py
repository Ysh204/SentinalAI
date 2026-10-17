from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.api.deps import build_container
from backend.app.core.config import load_settings
from backend.app.main import create_app


@pytest.fixture
def tmp_settings(tmp_path: Path):
    base = load_settings()
    return replace(
        base,
        ai_provider="mock",
        gemini_api_key=None,
        database_path=tmp_path / "test.db",
        workspace_root=tmp_path / "workspaces",
        log_level="WARNING",
    )


@pytest.fixture
def container(tmp_settings):
    return build_container(tmp_settings)


@pytest.fixture
def client(tmp_settings, container) -> TestClient:
    app = create_app(tmp_settings, container)
    return TestClient(app)


SAMPLE_PAYLOAD = {
    "title": "Sample: add() returns the wrong result",
    "error_message": "AssertionError: assert add(2, 3) == 5  (got -1)",
    "stack_trace": 'File "test_buggy_app.py", line 5, in test_add\n    assert add(2, 3) == 5',
    "repository_path": "sample_app",
}


BAD_PATCH = (
    "--- a/buggy_app.py\n"
    "+++ b/buggy_app.py\n"
    "@@ -10,1 +10,1 @@\n"
    "-    return f\"Hello, {name}\"\n"
    "+    return f\"Hi, {name}\"\n"
)
