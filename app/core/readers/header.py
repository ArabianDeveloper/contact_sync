"""Guess which row holds the column headers."""
from __future__ import annotations

from app.config import HEADER_SCAN_ROWS


def guess_header_row(rows: list[list[str]]) -> int:
    """Return the 0-based index of the most likely header row.

    Scanning starts at the first row that has any content, and covers the next
    HEADER_SCAN_ROWS rows. The header is the first row with the most cells that
    contain letters. A title row above the header has fewer such cells, and a data
    row has fewer because the phone cell has no letters.
    """
    start = next(
        (i for i, row in enumerate(rows) if any(cell.strip() for cell in row)),
        None,
    )
    if start is None:
        return 0

    best_index = start
    best_score = 0
    for index in range(start, min(start + HEADER_SCAN_ROWS, len(rows))):
        score = sum(1 for cell in rows[index] if any(ch.isalpha() for ch in cell))
        if score > best_score:
            best_index, best_score = index, score
    return best_index
