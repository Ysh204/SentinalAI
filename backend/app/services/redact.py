"""Redact secrets, tokens, credentials, and personal data across incident fields."""

from __future__ import annotations

import re
from typing import Any

_SECRET_KEYS = {
    "authorization",
    "api_key",
    "apikey",
    "password",
    "secret",
    "token",
    "card",
    "card_number",
    "cvv",
    "ssn",
    "credit_card",
}

_EMAIL = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
_CARD = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
_BEARER_OR_KEY = re.compile(
    r"\b(?:Bearer\s+[A-Za-z0-9_\-\.]{12,}|(?:api_key|token|secret)[=:\s]+[A-Za-z0-9_\-\.]{12,}|AIza[0-9A-Za-z-_]{35})\b",
    re.IGNORECASE,
)


def redact_text(text: str | None) -> str:
    if not text:
        return ""
    cleaned = _EMAIL.sub("[REDACTED_EMAIL]", text)
    cleaned = _CARD.sub("[REDACTED_CARD]", cleaned)
    cleaned = _BEARER_OR_KEY.sub("[REDACTED_SECRET]", cleaned)
    return cleaned


def redact_payload(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if str(key).lower() in _SECRET_KEYS:
                out[key] = "[REDACTED]"
            else:
                out[key] = redact_payload(item)
        return out
    if isinstance(value, list):
        return [redact_payload(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value
