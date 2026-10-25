"""Redact secrets and personal data from captured payloads."""

from __future__ import annotations

from victim_app.redact import redact as redact_payload

__all__ = ["redact_payload"]
