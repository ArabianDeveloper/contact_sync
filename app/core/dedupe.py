"""Removal of duplicate rows inside the file (same normalized phone)."""
from __future__ import annotations

from dataclasses import replace

from app.core.models import CleanRow, DuplicateRow


def remove_duplicates(rows: list[CleanRow]) -> tuple[list[CleanRow], list[DuplicateRow]]:
    """Keep the last row of each phone. The labels of all the rows of that phone are merged
    into the kept row. Returns (kept rows in file order, removed rows for the report).

    Only valid rows should be passed in.
    """
    groups: dict[str, list[CleanRow]] = {}
    for row in rows:
        groups.setdefault(row.phone, []).append(row)

    kept: list[CleanRow] = []
    duplicates: list[DuplicateRow] = []

    for group in groups.values():
        last = group[-1]
        if len(group) == 1:
            kept.append(last)
            continue

        merged: list[str] = []
        seen: set[str] = set()
        for row in group:
            for label in row.labels:
                key = label.casefold()
                if key not in seen:
                    seen.add(key)
                    merged.append(label)

        kept.append(replace(last, labels=merged))
        for row in group[:-1]:
            duplicates.append(
                DuplicateRow(
                    row_number=row.row_number,
                    kept_row_number=last.row_number,
                    name=row.name,
                    phone=row.phone,
                    labels=merged,
                )
            )

    kept.sort(key=lambda row: row.row_number)
    duplicates.sort(key=lambda row: row.row_number)
    return kept, duplicates
