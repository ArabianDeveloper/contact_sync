"""XLSX, XLS and ODS reader (python-calamine)."""
from __future__ import annotations

import logging
from pathlib import Path

from app.core.errors import ReadError
from app.core.models import SourceTable
from app.core.readers.cells import cell_to_text, trim_trailing_empty_rows

logger = logging.getLogger("contact_sync.core.readers")


def read_excel(path: Path, file_type: str, sheet: str | None = None) -> SourceTable:
    try:
        from python_calamine import CalamineWorkbook
    except ImportError as exc:
        raise ReadError("The library 'python-calamine' is not installed.") from exc

    label = file_type.upper()
    try:
        workbook = CalamineWorkbook.from_path(str(path))
        sheet_names = list(workbook.sheet_names)
        if not sheet_names:
            raise ReadError(f"The {label} file has no sheets.")

        sheet_name = sheet if sheet is not None else sheet_names[0]
        if sheet_name not in sheet_names:
            raise ReadError(f"The sheet '{sheet_name}' does not exist in the file.")

        # skip_empty_area=False keeps the row numbers the same as in the file.
        raw_rows = workbook.get_sheet_by_name(sheet_name).to_python(skip_empty_area=False)
    except ReadError:
        raise
    except Exception as exc:  # the library raises several different error types
        raise ReadError(f"The {label} file could not be read: {exc}") from exc

    rows = [[cell_to_text(cell) for cell in row] for row in raw_rows]
    rows = trim_trailing_empty_rows(rows)
    if not rows:
        raise ReadError(f"The sheet '{sheet_name}' has no data.")

    logger.info("Read %s file: sheets=%d, rows=%d", file_type, len(sheet_names), len(rows))
    return SourceTable(
        rows=rows,
        file_type=file_type,
        sheet_names=sheet_names,
        sheet_name=sheet_name,
    )
