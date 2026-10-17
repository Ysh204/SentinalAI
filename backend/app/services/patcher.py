"""Patch generation. Never writes into the original repository."""

from __future__ import annotations

import logging

from backend.app.core.exceptions import SentinelAIError
from backend.app.models.schemas import IncidentPublic
from backend.app.services.ai_provider import AIProvider
from backend.app.services.diff_utils import is_valid_unified_diff
from backend.app.services.source_context import collect_source_context, resolve_repository_path

LOGGER = logging.getLogger("sentinelai.patcher")


class Patcher:
    def __init__(self, provider: AIProvider, settings) -> None:
        self.provider = provider
        self.settings = settings

    def generate(self, incident: IncidentPublic) -> str:
        repo = resolve_repository_path(incident.repository_path, self.settings)
        source_context, _files = collect_source_context(repo)
        try:
            draft = self.provider.generate_patch(incident, source_context)
        except SentinelAIError:
            raise
        except Exception as exc:
            LOGGER.exception("Patcher provider failed")
            raise SentinelAIError(
                "Patch provider failed. No patch was stored as success.",
                code="patcher_failed",
                status_code=502,
            ) from exc

        diff = (draft.unified_diff or "").strip()
        if not diff:
            raise SentinelAIError(
                draft.notes or "No usable patch is available for this incident.",
                code="no_patch",
                status_code=422,
            )
        if not is_valid_unified_diff(diff):
            raise SentinelAIError(
                "Provider returned a patch that is not a valid unified diff. It was not stored.",
                code="invalid_diff",
                status_code=422,
            )
        return diff if diff.endswith("\n") else diff + "\n"
