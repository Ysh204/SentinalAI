"""Unified-diff validation and safe application inside a workspace."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from backend.app.core.exceptions import SentinelAIError

HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
PROTECTED_NAMES = {
    "conftest.py",
    "pytest.ini",
    "pyproject.toml",
    "setup.cfg",
    "setup.py",
    "tox.ini",
    "sitecustomize.py",
    "usercustomize.py",
    ".coveragerc",
    "__init__.py",
}


@dataclass
class FilePatch:
    path: str
    hunks: list[str]


def is_valid_unified_diff(diff: str) -> bool:
    if not diff or not diff.strip():
        return False
    has_old = bool(re.search(r"^---\s+\S+", diff, re.MULTILINE))
    has_new = bool(re.search(r"^\+\+\+\s+\S+", diff, re.MULTILINE))
    has_hunk = bool(re.search(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", diff, re.MULTILINE))
    return has_old and has_new and has_hunk


def _strip_prefix(path: str) -> str:
    cleaned = path.strip()
    if cleaned.startswith("a/") or cleaned.startswith("b/"):
        cleaned = cleaned[2:]
    return cleaned.replace("\\", "/")


def is_protected_file(path_str: str) -> bool:
    cleaned = _strip_prefix(path_str)
    path = Path(cleaned)
    name = path.name.lower()
    if name in PROTECTED_NAMES:
        return True
    if name.endswith(".pth"):
        return True
    if name.startswith(".env"):
        return True
    if name.startswith("test_") or name.endswith("_test.py"):
        return True
    if any(part.lower() in {"tests", "test", ".git", ".github", "fixtures"} for part in path.parts):
        return True
    return False


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
    try:
        if not target.is_relative_to(workspace_resolved) or target == workspace_resolved:
            raise SentinelAIError("Patch would write outside the workspace.", code="unsafe_patch")
    except AttributeError:
        if not str(target).startswith(str(workspace_resolved) + os.sep):
            raise SentinelAIError("Patch would write outside the workspace.", code="unsafe_patch") from None
    return target


def parse_file_patches(diff: str) -> list[FilePatch]:
    lines = diff.replace("\r\n", "\n").split("\n")
    files: list[FilePatch] = []
    current_path: str | None = None
    current_hunks: list[str] = []
    hunk_lines: list[str] = []

    remaining_old = 0
    remaining_new = 0
    in_hunk = False

    def flush_hunk() -> None:
        nonlocal hunk_lines, in_hunk, remaining_old, remaining_new
        if hunk_lines:
            current_hunks.append("\n".join(hunk_lines))
            hunk_lines = []
        in_hunk = False
        remaining_old = 0
        remaining_new = 0

    def flush_file() -> None:
        nonlocal current_path, current_hunks
        flush_hunk()
        if current_path and current_hunks:
            files.append(FilePatch(path=current_path, hunks=list(current_hunks)))
        current_path = None
        current_hunks = []

    i = 0
    num_lines = len(lines)
    while i < num_lines:
        line = lines[i]

        # Check for file header (--- a/... followed by +++ b/...)
        is_file_header = False
        if line.startswith("--- "):
            if not in_hunk or (remaining_old <= 0 and remaining_new <= 0):
                # Verify if next non-empty line starts with +++
                for next_idx in range(i + 1, min(i + 4, num_lines)):
                    if lines[next_idx].startswith("+++ "):
                        is_file_header = True
                        break

        if is_file_header:
            flush_file()
            # Advance to the +++ line
            i += 1
            while i < num_lines and not lines[i].startswith("+++ "):
                i += 1
            if i < num_lines:
                raw = lines[i][4:].strip()
                if "\t" in raw:
                    raw = raw.split("\t", 1)[0]
                current_path = _strip_prefix(raw)
            i += 1
            continue

        hunk_match = HUNK_RE.match(line)
        if hunk_match and current_path:
            flush_hunk()
            in_hunk = True
            old_count = int(hunk_match.group(2)) if hunk_match.group(2) is not None else 1
            new_count = int(hunk_match.group(4)) if hunk_match.group(4) is not None else 1
            remaining_old = old_count
            remaining_new = new_count
            hunk_lines = [line]
            i += 1
            continue

        if in_hunk:
            if line.startswith("-"):
                hunk_lines.append(line)
                remaining_old = max(0, remaining_old - 1)
            elif line.startswith("+"):
                hunk_lines.append(line)
                remaining_new = max(0, remaining_new - 1)
            elif line.startswith(" ") or line == "":
                hunk_lines.append(line)
                remaining_old = max(0, remaining_old - 1)
                remaining_new = max(0, remaining_new - 1)
            elif line.startswith("\\"):
                hunk_lines.append(line)
            else:
                # Unexpected line outside hunk convention ends the hunk
                flush_hunk()

            if remaining_old == 0 and remaining_new == 0 and hunk_lines:
                # Peek if next line is another hunk or file header
                if i + 1 < num_lines and (lines[i + 1].startswith("@@ ") or lines[i + 1].startswith("--- ")):
                    flush_hunk()
            i += 1
            continue

        i += 1

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
        if is_protected_file(file_patch.path):
            raise SentinelAIError(
                f"Modifying test or configuration files is prohibited: {file_patch.path}",
                code="protected_file_modified",
                status_code=403,
            )
        target = _safe_join(workspace, file_patch.path)
        if not target.exists():
            has_deletions = any(
                any(line.startswith("-") for line in hunk.split("\n")[1:])
                for hunk in file_patch.hunks
            )
            if has_deletions:
                raise SentinelAIError(
                    f"Patch targets missing file: {file_patch.path}",
                    code="patch_target_missing",
                )
            original = []
            has_crlf = False
            has_trailing_nl = True
        else:
            raw_bytes = target.read_bytes()
            has_crlf = b"\r\n" in raw_bytes
            has_trailing_nl = raw_bytes.endswith((b"\n", b"\r"))
            original = raw_bytes.decode("utf-8").splitlines()

        updated = _apply_hunks(original, file_patch.hunks)

        target.parent.mkdir(parents=True, exist_ok=True)
        newline = "\r\n" if has_crlf else "\n"
        body = newline.join(updated)
        if has_trailing_nl and updated:
            body += newline
        target.write_bytes(body.encode("utf-8"))
        changed.append(file_patch.path)
    return changed


def _apply_hunks(original: list[str], hunks: list[str]) -> list[str]:
    result = list(original)
    parsed: list[tuple[int, list[str]]] = []
    for hunk in hunks:
        lines = hunk.split("\n")
        header = lines[0]
        match = HUNK_RE.match(header)
        if not match:
            raise SentinelAIError("Malformed hunk header in patch.", code="invalid_diff")
        start = int(match.group(1))
        parsed.append((start, lines[1:]))
    # Apply from bottom to top so earlier line numbers stay valid.
    parsed.sort(key=lambda item: item[0], reverse=True)
    for start, body in parsed:
        result = _apply_single_hunk(result, start, body)
    return result


def _apply_single_hunk(original: list[str], start: int, body: list[str]) -> list[str]:
    while body and body[-1] == "":
        body = body[:-1]

    # Extract pattern of old lines to match against original
    old_pattern: list[str] = []
    for raw in body:
        if raw.startswith("\\"):
            continue
        if not raw:
            old_pattern.append("")
        elif raw[0] in {" ", "-"}:
            old_pattern.append(raw[1:])

    # Try requested index first
    target_idx = max(start - 1, 0)
    matched_idx: int | None = None

    if not old_pattern:
        matched_idx = target_idx
    else:
        pat_len = len(old_pattern)
        if target_idx + pat_len <= len(original) and original[target_idx : target_idx + pat_len] == old_pattern:
            matched_idx = target_idx
        else:
            # Fuzz search within a ±25 line window or file-wide if small
            search_window = range(
                max(0, target_idx - 25),
                min(len(original) - pat_len + 1, target_idx + 26),
            )
            candidates = [idx for idx in search_window if original[idx : idx + pat_len] == old_pattern]
            if len(candidates) == 1:
                matched_idx = candidates[0]
            elif not candidates:
                # File wide search if unique
                all_matches = [
                    idx for idx in range(len(original) - pat_len + 1) if original[idx : idx + pat_len] == old_pattern
                ]
                if len(all_matches) == 1:
                    matched_idx = all_matches[0]

    if matched_idx is None:
        matched_idx = target_idx

    output = original[:matched_idx]
    cursor = matched_idx

    for raw in body:
        if raw.startswith("\\"):
            continue
        if not raw:
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
