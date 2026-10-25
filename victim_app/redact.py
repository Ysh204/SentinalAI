"""Strip secrets and personal data from captured checkout payloads."""

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
_EMAIL = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
_CARD = re.compile(r"\b(?:\d[ -]*?){13,16}\b")


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if str(key).lower() in _SECRET_KEYS:
                out[key] = "[REDACTED]"
            else:
                out[key] = redact(item)
        return out
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        text = _EMAIL.sub("[REDACTED_EMAIL]", value)
        return _CARD.sub("[REDACTED_CARD]", text)
    return value
