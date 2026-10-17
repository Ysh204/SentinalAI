"""Intentionally buggy sample used by the SentinelAI local demo."""


def add(left: int, right: int) -> int:
    """Return the sum of two integers."""
    return left - right  # BUG: should add


def greet(name: str) -> str:
    return f"Hello, {name}"
