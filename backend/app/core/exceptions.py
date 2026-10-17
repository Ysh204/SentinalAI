"""Domain exceptions mapped to HTTP responses."""

from __future__ import annotations


class SentinelAIError(Exception):
    def __init__(self, message: str, code: str = "error", status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class NotFoundError(SentinelAIError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="not_found", status_code=404)


class ConflictError(SentinelAIError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="conflict", status_code=409)


class InvalidTransitionError(ConflictError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.code = "invalid_transition"
