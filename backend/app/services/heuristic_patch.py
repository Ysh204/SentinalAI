"""Offline patches synthesized from the current source, not frozen line numbers."""

from __future__ import annotations

import difflib
import re
from pathlib import Path

_LINE_TOTAL_RETURN = re.compile(
    r"(^def _line_total\([^\n]+\n(?:[ \t]+[^\n]*\n)*?)"
    r"([ \t]+)return int\(item\[\"price\"\]\) \* int\(item\[\"qty\"\]\)",
    re.MULTILINE,
)
_ADD_BUG = re.compile(r"^([ \t]*)return left - right[^\n]*$", re.MULTILINE)


def parse_source_context(source_context: str) -> dict[str, str]:
    files: dict[str, str] = {}
    if not source_context.strip():
        return files
    chunks = re.split(r"(?m)^--- ", source_context)
    for chunk in chunks:
        chunk = chunk.strip("\n")
        if not chunk:
            continue
        header, sep, body = chunk.partition("\n")
        if not sep:
            continue
        name = header.strip().replace("\\", "/")
        files[name] = body
    return files


def unified_diff(path: str, before: str, after: str) -> str:
    old = before.splitlines(keepends=True)
    new = after.splitlines(keepends=True)
    if old and not old[-1].endswith("\n"):
        old[-1] += "\n"
    if new and not new[-1].endswith("\n"):
        new[-1] += "\n"
    diff = difflib.unified_diff(old, new, fromfile=f"a/{path}", tofile=f"b/{path}", lineterm="\n")
    return "".join(diff)


def guard_none_cart_line(source: str) -> str | None:
    if "if item is None" in source and "def _line_total" in source:
        return None
    match = _LINE_TOTAL_RETURN.search(source)
    if not match:
        return None
    indent = match.group(2)
    replacement = (
        f"{match.group(1)}{indent}if item is None:\n"
        f"{indent}    return 0\n"
        f"{indent}return int(item[\"price\"]) * int(item[\"qty\"])"
    )
    return _LINE_TOTAL_RETURN.sub(replacement, source, count=1)


def fix_sample_add(source: str) -> str | None:
    if "return left + right" in source and "return left - right" not in source:
        return None
    if not _ADD_BUG.search(source):
        return None
    return _ADD_BUG.sub(r"\1return left + right", source, count=1)


def synthesize(source_context: str) -> tuple[str, str] | None:
    files = parse_source_context(source_context)
    if "shop.py" in files:
        updated = guard_none_cart_line(files["shop.py"])
        if updated:
            return unified_diff("shop.py", files["shop.py"], updated), (
                "Inserted a None guard in _line_total from the current shop.py source."
            )
    for name, content in files.items():
        if Path(name).name == "buggy_app.py" or "def add(" in content:
            updated = fix_sample_add(content)
            if updated:
                return unified_diff(name, content, updated), (
                    "Replaced subtraction with addition in add() from the current sample source."
                )
    return None
