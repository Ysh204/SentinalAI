"""Thin LLM wrapper: one model in, validated JSON out."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from backend.app.core.exceptions import SentinelAIError

LOGGER = logging.getLogger("sentinelai.llm")
T = TypeVar("T", bound=BaseModel)


def strip_fences(text: str) -> str:
    stripped = text.strip()
    match = re.search(r"```(?:json|diff)?\s*(.*?)```", stripped, re.DOTALL)
    if match:
        return match.group(1).strip()
    return stripped


def parse_json_object(text: str) -> dict[str, Any]:
    candidate = strip_fences(text)
    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", candidate, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass
    return {}


def parse_model(text: str, model: type[T], *, retries_exhausted: bool = False) -> T:
    data = parse_json_object(text)
    if not data:
        raise SentinelAIError(
            "LLM did not return JSON. No result was stored as success.",
            code="malformed_llm_json",
            status_code=502,
        )
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        LOGGER.warning("LLM JSON failed schema validation: %s", exc)
        if retries_exhausted:
            raise SentinelAIError(
                "LLM JSON failed schema validation after retry.",
                code="malformed_llm_json",
                status_code=502,
            ) from exc
        raise
