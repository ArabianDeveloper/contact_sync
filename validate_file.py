"""Stage 2 test tool: reads a file, suggests the mapping, validates, removes duplicates.

Usage:
    python validate_file.py "path\to\file.csv"
    python validate_file.py "path\to\file.xlsx" --sheet "Sheet2" --header-row 3
    python validate_file.py "file.csv" --name-cols 1,2,3 --phone 4 --email 5 --labels 6
(column numbers start at 1)
"""
from __future__ import annotations

import argparse
import sys

from app.core.cleaning import NameOptions
from app.core.errors import ContactSyncError
from app.core.header_suggest import suggest_mapping
from app.core.models import Mapping
from app.core.pipeline import process_table
from app.core.readers import read_file


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Validate a data file.")
    parser.add_argument("path")
    parser.add_argument("--sheet", default=None)
    parser.add_argument("--header-row", type=int, default=None, help="1 = first row")
    parser.add_argument("--name-cols", default=None, help="for example 1,2,3 (in joining order)")
    parser.add_argument("--phone", type=int, default=None)
    parser.add_argument("--email", type=int, default=None)
    parser.add_argument("--labels", type=int, default=None)
    parser.add_argument("--show", type=int, default=5, help="valid rows to show")
    args = parser.parse_args()

    try:
        table = read_file(args.path, sheet=args.sheet)
        if args.header_row is not None:
            table.set_header_row(args.header_row - 1)
        headers = table.headers()

        mapping = suggest_mapping(headers)
        if args.name_cols:
            mapping.name_columns = [int(x) - 1 for x in args.name_cols.split(",")]
        if args.phone:
            mapping.phone_column = args.phone - 1
        if args.email:
            mapping.email_column = args.email - 1
        if args.labels:
            mapping.labels_column = args.labels - 1

        def title(index):
            return f"{index + 1} ({headers[index]})" if index is not None else "NOT FOUND"

        print("Mapping:")
        print("  Name columns :", ", ".join(title(i) for i in mapping.name_columns) or "NOT FOUND")
        print("  Phone        :", title(mapping.phone_column))
        print("  Email        :", title(mapping.email_column))
        print("  Labels       :", title(mapping.labels_column))
        if not mapping.is_complete():
            print("\nThe mapping is incomplete. Use --name-cols, --phone, --email, --labels.")
            return 1

        result = process_table(table, mapping, NameOptions())
    except ContactSyncError as exc:
        print(f"ERROR: {exc}")
        return 1

    print()
    print(f"Total rows        : {result.total_rows}")
    print(f"Valid rows        : {result.valid_count}")
    print(f"Rejected rows     : {result.rejected_count}")
    print(f"Duplicates removed: {result.duplicate_count}")
    print(f"Distinct labels   : {len(result.distinct_labels())}")

    if result.rejected:
        print("\nRejected rows:")
        for row in result.rejected:
            print(f"  row {row.row_number}: {', '.join(row.reasons)}  "
                  f"[{row.name!r}, {row.phone!r}, {row.email!r}, {row.labels!r}]")
    if result.duplicates:
        print("\nRemoved duplicates:")
        for row in result.duplicates:
            print(f"  row {row.row_number} -> kept row {row.kept_row_number}  "
                  f"{row.phone}  labels now: {row.labels}")
    if result.valid_rows:
        print(f"\nFirst {args.show} valid rows:")
        for row in result.valid_rows[:args.show]:
            print(f"  row {row.row_number}: {row.name} | {row.phone} | {row.email} | {row.labels}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
