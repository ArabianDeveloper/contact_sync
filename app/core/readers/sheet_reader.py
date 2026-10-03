"""Google Sheet reader. The service object is passed in, so this module has no Google imports."""
from __future__ import annotations

import logging
import re

from app.core.errors import ReadError
from app.core.models import SourceTable
from app.core.readers.cells import cell_to_text, trim_trailing_empty_rows
from app.core.readers.header import guess_header_row
from app.services import sheets

logger = logging.getLogger("contact_sync.core.readers")

_RANGE_START = re.compile(r"^\$?([A-Za-z]{1,3})?\$?(\d+)?")


def range_offsets(cell_range: str | None) -> tuple[int, int]:
    """(rows, columns) before the first cell of the range, so row numbers stay the same as in
    the sheet. 'C5:F9' -> (4, 2). Without a range -> (0, 0)."""
    if not cell_range:
        return 0, 0
    match = _RANGE_START.match(cell_range.strip())
    letters, digits = (match.group(1), match.group(2)) if match else (None, None)
    column = 0
    for ch in (letters or "").upper():
        column = column * 26 + (ord(ch) - 64)
    row = int(digits) if digits else 1
    return max(row - 1, 0), max(column - 1, 0)


def read_sheet(service, text: str, sheet: str | None = None, cell_range: str | None = None) -> SourceTable:
    """Read a Google Sheet given its link or ID. `sheet` is the tab (the first one by default)."""
    sheet_id = sheets.parse_sheet_id(text)
    if sheet_id is None:
        raise ReadError("Enter a Google Sheet link or ID.")
    cell_range = (cell_range or "").strip() or None
    if cell_range and "!" in cell_range:
        raise ReadError("Enter the range without the tab name, for example A1:F200.")

    try:
        tabs = sheets.list_tabs(service, sheet_id)
        if not tabs:
            raise ReadError("The spreadsheet has no tabs.")
        tab = sheet if sheet is not None else tabs[0]
        if tab not in tabs:
            raise ReadError(f"The tab '{tab}' does not exist in the spreadsheet.")
        values = sheets.read_values(service, sheet_id, tab, cell_range)
    except ReadError:
        raise
    except Exception as exc:
        raise sheets.read_error(exc, with_range=bool(cell_range)) from exc

    row_offset, column_offset = range_offsets(cell_range)
    rows = [[""] * column_offset + [cell_to_text(c) for c in row] for row in values]
    rows = [[] for _ in range(row_offset)] + rows
    rows = trim_trailing_empty_rows(rows)
    if not rows:
        raise ReadError(f"The tab '{tab}' has no data.")

    logger.info("Read Google Sheet: tabs=%d, rows=%d", len(tabs), len(rows))
    return SourceTable(
        rows=rows, file_type="gsheet", source_name=sheet_id, sheet_names=tabs, sheet_name=tab,
        header_row=guess_header_row(rows),
    )
