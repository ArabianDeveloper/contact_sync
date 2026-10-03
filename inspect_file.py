"""Stage 1 test tool: shows how the program reads a data file.

Usage:
    python inspect_file.py "path\to\file.xlsx"
    python inspect_file.py "path\to\file.xlsx" --sheet "Sheet2"
    python inspect_file.py "path\to\file.csv" --header-row 3 --rows 20
"""
from __future__ import annotations

import argparse
import sys

from app.core.errors import ContactSyncError
from app.core.readers import read_file


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Show how a data file is read.")
    parser.add_argument("path")
    parser.add_argument("--sheet", default=None, help="sheet name (XLSX, XLS, ODS)")
    parser.add_argument("--header-row", type=int, default=None,
                        help="header row number as shown in the file (1 = first row)")
    parser.add_argument("--rows", type=int, default=10, help="number of data rows to show")
    args = parser.parse_args()

    try:
        table = read_file(args.path, sheet=args.sheet)
    except ContactSyncError as exc:
        print(f"ERROR: {exc}")
        return 1

    if args.header_row is not None:
        table.set_header_row(args.header_row - 1)

    print(f"File type     : {table.file_type}")
    print(f"Encoding      : {table.encoding or '-'}")
    print(f"Delimiter     : {repr(table.delimiter) if table.delimiter else '-'}")
    print(f"Sheets        : {', '.join(table.sheet_names) if table.sheet_names else '-'}")
    print(f"Selected sheet: {table.sheet_name or '-'}")
    print(f"Total rows    : {len(table.rows)}")
    print(f"Header row    : {table.header_row + 1}")
    print(f"Columns       : {table.column_count}")
    print()
    print("Headers:")
    for index, header in enumerate(table.headers(), start=1):
        print(f"  {index}. {header}")
    print()
    print(f"First {args.rows} data rows (row number in the file, then the values):")
    shown = 0
    for row_number, row in table.data_rows():
        print(f"  {row_number}: {row}")
        shown += 1
        if shown >= args.rows:
            break
    if shown == 0:
        print("  (no data rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
