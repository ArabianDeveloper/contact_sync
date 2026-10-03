"""Conversion of cell values to text."""
from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta
from typing import Any


def cell_to_text(value: Any) -> str:
    """Convert a cell value to text.

    Whole numbers lose the decimal part (Excel stores 99123456 as 99123456.0).
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return ""
        if value.is_integer():
            return str(int(value))
        return repr(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, timedelta):
        return str(value)
    return str(value)


def trim_trailing_empty_rows(rows: list[list[str]]) -> list[list[str]]:
    end = len(rows)
    while end > 0 and not any(cell.strip() for cell in rows[end - 1]):
        end -= 1
    return rows[:end]
