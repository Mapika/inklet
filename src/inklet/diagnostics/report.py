"""Plain-text rendering of a diagnostic list.

Optimised for two readers with the same needs: a terminal and an agent's
context window. One line per finding, grouped by severity, codes in a fixed
column so the eye (or a regex) can find them, and a count on the first line so
"did that fix it?" is answerable without reading the body.
"""

from __future__ import annotations

from typing import Sequence

from .rules import SEVERITIES, Diagnostic

__all__ = ["format_report"]

_ANSI = {"error": "\x1b[31m", "warning": "\x1b[33m", "info": "\x1b[90m"}
_RESET = "\x1b[0m"
_BOLD = "\x1b[1m"
_MIN_CODE_WIDTH = 14


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def format_report(diags: Sequence[Diagnostic], *, color: bool = False) -> str:
    """Compact report. Returns a single string with no trailing newline."""
    if not diags:
        headline = "inklet lint: clean, 0 diagnostics"
        return f"{_BOLD}{headline}{_RESET}" if color else headline

    counts = {name: sum(1 for d in diags if d.severity == name) for name in SEVERITIES}
    other = [d for d in diags if d.severity not in SEVERITIES]
    summary = ", ".join(_plural(counts[name], name) for name in SEVERITIES
                        if counts[name])
    if other:
        summary += f", {_plural(len(other), 'unknown-severity finding')}"

    width = max(_MIN_CODE_WIDTH, max(len(d.code) for d in diags))
    lines = [f"{_BOLD}inklet lint: {summary}{_RESET}" if color
             else f"inklet lint: {summary}"]

    for name in list(SEVERITIES) + (["other"] if other else []):
        group = other if name == "other" else [d for d in diags if d.severity == name]
        if not group:
            continue
        tint = _ANSI.get(name, "") if color else ""
        reset = _RESET if color and tint else ""
        lines.append("")
        lines.append(f"{tint}{name.upper()}{reset}" if tint else name.upper())
        for diag in group:
            body = diag.message
            if diag.hint:
                body += f"  -> {diag.hint}"
            lines.append(f"  {tint}{diag.code.ljust(width)}{reset}  {body}")

    return "\n".join(lines)
