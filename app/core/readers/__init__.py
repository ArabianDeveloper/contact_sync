"""File readers. Use read_file(); it detects the type by itself."""
from __future__ import annotations

from pathlib import Path

from app.core.models import SourceTable
from app.core.readers.csv_reader import read_csv
from app.core.readers.detector import detect_file_type
from app.core.readers.excel_reader import read_excel
from app.core.readers.header import guess_header_row
from app.core.readers.json_reader import read_json

__all__ = ["read_file", "detect_file_type"]


def read_file(path: str | Path, sheet: str | None = None) -> SourceTable:
    """Detect the file type, read the file, and guess the header row.

    `sheet` is used only for XLSX, XLS and ODS (the first sheet is the default).
    """
    path = Path(path)
    file_type = detect_file_type(path)

    if file_type in ("xlsx", "xls", "ods"):
        table = read_excel(path, file_type, sheet)
    elif file_type in ("csv", "tsv"):
        table = read_csv(path)
    else:
        table = read_json(path)

    table.source_name = path.name
    table.header_row = guess_header_row(table.rows)
    return table
