"""Text shown in the result tables. No Qt code."""
from __future__ import annotations

from app.core.models import RunSummary

_STEP_NAMES = {"contact": "Contact", "label": "Label", "space": "Space"}


def format_rows(rows: list[int], limit: int = 20) -> str:
    """'2, 5, 9' or '2, 5, 9, ... (+30 more)'."""
    shown = ", ".join(str(r) for r in rows[:limit])
    return shown if len(rows) <= limit else f"{shown}, ... (+{len(rows) - limit} more)"


def failed_table(summary: RunSummary) -> list[list]:
    return [
        [item.row_number, item.name, _STEP_NAMES.get(item.step, item.step), item.target or "", item.message]
        for item in summary.failed
    ]


def reported_table(summary: RunSummary) -> list[list]:
    """One line per missing label or space: what, name, number of rows, the rows, the reason."""
    reasons: dict[tuple[str, str], str] = {}
    for item in summary.reported:
        reasons.setdefault((item.step, item.target or ""), item.message)
    return [
        [_STEP_NAMES.get(step, step), target, len(rows), format_rows(rows), reasons[(step, target)]]
        for step, target, rows in summary.reported_by_target()
    ]


def not_processed_table(summary: RunSummary) -> list[list]:
    return [[row] for row in summary.not_processed]


def banner(summary: RunSummary) -> tuple[str, str]:
    """(style name, text) for the line above the results."""
    if summary.stopped:
        return "error", f"The import was stopped: {summary.stopped_reason}"
    if summary.cancelled:
        return "warning", (f"The import was cancelled. {len(summary.not_processed)} rows were not processed.")
    if summary.failed_count or summary.reported:
        return "warning", "The import is complete, with some problems (see the tables below)."
    return "success", "The import is complete."


def describe_space(info) -> str:
    """One line for the space choice list."""
    created = (info.create_time or "")[:10] or "-"
    members = "-" if info.member_count is None else str(info.member_count)
    return f"{info.name}   |   created {created}   |   members {members}"
