"""Helpers for concise orchestrator activity log lines."""

from __future__ import annotations

import json
from typing import Any


def first_non_empty_line(*texts: str) -> str:
    """Return the first non-blank line from one or more text blobs."""
    for text in texts:
        for line in text.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped
    return ""


def truncate_line(line: str, *, max_len: int = 120) -> str:
    if len(line) <= max_len:
        return line
    return line[: max_len - 1] + "…"


def first_line_from_command_payload(payload: dict[str, Any]) -> str:
    return first_non_empty_line(
        str(payload.get("stdout", "")),
        str(payload.get("stderr", "")),
    )


def parse_tool_result(result: str) -> dict[str, Any]:
    try:
        parsed = json.loads(result)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def format_command_started(command: str, *, cwd: str | None = None) -> str:
    cwd_part = f" (cwd={cwd})" if cwd else ""
    return f"$ {command}{cwd_part}"


def format_command_finished(
    *,
    exit_code: int | str,
    stdout: str = "",
    stderr: str = "",
) -> str:
    first = truncate_line(first_non_empty_line(stdout, stderr))
    if first:
        return f"exit {exit_code} — {first}"
    return f"exit {exit_code}"
