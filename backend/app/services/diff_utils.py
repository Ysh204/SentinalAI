"""Unified-diff validation and safe application inside a workspace."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from backend.app.core.exceptions import SentinelAIError

HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", re.MULTILINE)


@dataclass
class FilePatch:
    path: str
    hunks: list[str]


def is_valid_unified_diff(diff: str) -> bool:
    if not diff or not diff.strip():
        return False
    has_old = bool(re.search(r"^---\s+\S+", diff, re.MULTILINE))
    has_new = bool(re.search(r"^\+\+\+\s+\S+", diff, re.MULTILINE))
    has_hunk = bool(HUNK_RE.search(diff))
    return has_old and has_new and has_hunk


def _strip_prefix(path: str) -> str:
    cleaned = path.strip()
    if cleaned.startswith("a/") or cleaned.startswith("b/"):
        cleaned = cleaned[2:]
    return cleaned.replace("\\", "/")


def _safe_join(workspace: Path, relative: str) -> Path:
    if not relative or relative.endswith("/"):
        raise SentinelAIError("Patch contains an invalid file path.", code="unsafe_patch")
    if Path(relative).is_absolute() or relative.startswith("/"):
        raise SentinelAIError("Patch must use relative file paths.", code="unsafe_patch")
    parts = Path(relative).parts
    if ".." in parts:
        raise SentinelAIError("Patch path traversal is not allowed.", code="unsafe_patch")
    target = (workspace / relative).resolve()
    workspace_resolved = workspace.resolve()
    if not str(target).startswith(str(workspace_resolved)):
        raise SentinelAIError("Patch would write outside the workspace.", code="unsafe_patch")
    return target


def parse_file_patches(diff: str) -> list[FilePatch]:
    lines = diff.replace("\r\n", "\n").split("\n")
    files: list[FilePatch] = []
    current_path: str | None = None
    current_hunks: list[str] = []
    collecting = False
    hunk_lines: list[str] = []

    def flush_hunk() -> None:
        nonlocal hunk_lines
        if hunk_lines:
            current_hunks.append("\n".join(hunk_lines))
            hunk_lines = []

    def flush_file() -> None:
        nonlocal current_path, current_hunks
        flush_hunk()
        if current_path and current_hunks:
            files.append(FilePatch(path=current_path, hunks=list(current_hunks)))
        current_path = None
        current_hunks = []

    for line in lines:
        if line.startswith("--- "):
            flush_file()
            collecting = True
            continue
        if line.startswith("+++ ") and collecting:
            raw = line[4:].strip()
            if "\t" in raw:
                raw = raw.split("\t", 1)[0]
            current_path = _strip_prefix(raw)
            continue
        if line.startswith("@@ ") and current_path:
            flush_hunk()
            hunk_lines = [line]
            continue
        if hunk_lines:
            if line.startswith(("+", "-", " ", "\\")):
                hunk_lines.append(line)
            elif line == "":
                hunk_lines.append(line)
    flush_file()
    if not files:
        raise SentinelAIError("Diff did not contain any usable file hunks.", code="invalid_diff")
    return files


def apply_unified_diff(diff: str, workspace: Path) -> list[str]:
    """Apply a unified diff inside workspace. Returns relative paths changed."""
    if not is_valid_unified_diff(diff):
        raise SentinelAIError("Proposed patch is not a valid unified diff.", code="invalid_diff")

    changed: list[str] = []
    for file_patch in parse_file_patches(diff):
        target = _safe_join(workspace, file_patch.path)
        if not target.exists():
            raise SentinelAIError(
                f"Patch targets missing file: {file_patch.path}",
                code="patch_target_missing",
            )
        original = target.read_text(encoding="utf-8").splitlines()
        updated = _apply_hunks(original, file_patch.hunks)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(updated) + ("\n" if updated else ""), encoding="utf-8")
        changed.append(file_patch.path)
    return changed


def _apply_hunks(original: list[str], hunks: list[str]) -> list[str]:
    result = list(original)
    # Apply from bottom to top so earlier line numbers stay valid.
    parsed: list[tuple[int, list[str]]] = []
    for hunk in hunks:
        lines = hunk.split("\n")
        header = lines[0]
        match = HUNK_RE.match(header)
        if not match:
            raise SentinelAIError("Malformed hunk header in patch.", code="invalid_diff")
        start = int(match.group(1))
        parsed.append((start, lines[1:]))
    parsed.sort(key=lambda item: item[0], reverse=True)
    for start, body in parsed:
        result = _apply_single_hunk(result, start, body)
    return result


def _apply_single_hunk(original: list[str], start: int, body: list[str]) -> list[str]:
    index = max(start - 1, 0)
    output = original[:index]
    cursor = index
    while body and body[-1] == "":
        body = body[:-1]
    for raw in body:
        if raw.startswith("\\"):  # "\ No newline at end of file"
            continue
        if not raw:
            # blank line inside hunk is context with a missing leading space
            if cursor >= len(original) or original[cursor] != "":
                raise SentinelAIError("Patch context did not match the source file.", code="patch_mismatch")
            output.append("")
            cursor += 1
            continue
        tag, content = raw[0], raw[1:]
        if tag == " ":
            if cursor >= len(original) or original[cursor] != content:
                raise SentinelAIError("Patch context did not match the source file.", code="patch_mismatch")
            output.append(content)
            cursor += 1
        elif tag == "-":
            if cursor >= len(original) or original[cursor] != content:
                raise SentinelAIError("Patch context did not match the source file.", code="patch_mismatch")
            cursor += 1
        elif tag == "+":
            output.append(content)
        else:
            raise SentinelAIError("Unexpected hunk line in patch.", code="invalid_diff")
    output.extend(original[cursor:])
    return output
