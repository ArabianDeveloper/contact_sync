"""Stage 5 test tool: runs a full import from a file to your real Google account.

Usage (sign in first with google_check.py login):
    python run_import.py "path\to\file.xlsx" --limit 3
    python run_import.py "file.csv" --header-row 2 --name-cols 1,2,3 --phone 4 --email 5 --labels 6
    python run_import.py "file.csv" --limit 3 --no-create-labels --no-create-spaces

--limit N imports only the first N valid rows (use a small number for the first tests).
Press Ctrl+C during the import to cancel: the row in progress is finished, then it stops.
THIS CREATES REAL DATA after you confirm.
"""
from __future__ import annotations

import argparse
import sys
import threading

from app.core.cleaning import NameOptions
from app.core.errors import ContactSyncError
from app.core.header_suggest import suggest_mapping
from app.core.pipeline import process_table
from app.core.readers import read_file
from app.runner.import_runner import ImportRunner, RunCancelled, RunOptions
from app.services import auth
from app.services.chat import ChatService
from app.services.contacts import ContactsService
from app.settings import load_settings
from google_try import choose_space


def print_summary(summary) -> None:
    print("\n========== Results ==========")
    print(f"Rows processed         : {summary.processed_rows} of {summary.total_rows}")
    print(f"Contacts created       : {summary.contacts_created}")
    print(f"Contacts already there : {summary.contacts_existing}")
    print(f"Added to labels        : {summary.added_to_labels}   (already in label: {summary.already_in_labels}, labels created: {summary.labels_created})")
    print(f"Added to spaces        : {summary.added_to_spaces}   (already in space: {summary.already_in_spaces}, spaces created: {summary.spaces_created})")
    print(f"Failed                 : {summary.failed_count}")
    if summary.cancelled:
        print("The import was CANCELLED.")
    if summary.stopped:
        print(f"The import was STOPPED: {summary.stopped_reason}")
    if summary.failed:
        print("\nFailed items:")
        for item in summary.failed:
            target = f" '{item.target}'" if item.target else ""
            print(f"  row {item.row_number} ({item.name}) - {item.step}{target}: {item.message}")
    if summary.reported:
        print("\nReported (not found, nothing was created):")
        for step, target, rows in summary.reported_by_target():
            print(f"  {step} '{target}': rows {rows}")
    if summary.not_processed:
        print(f"\nNot processed rows: {summary.not_processed}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Import a data file to Google Contacts and Chat.")
    parser.add_argument("path")
    parser.add_argument("--sheet", default=None)
    parser.add_argument("--header-row", type=int, default=None, help="1 = first row")
    parser.add_argument("--name-cols", default=None, help="for example 1,2,3 (in joining order)")
    parser.add_argument("--phone", type=int, default=None)
    parser.add_argument("--email", type=int, default=None)
    parser.add_argument("--labels", type=int, default=None)
    parser.add_argument("--limit", type=int, default=None, help="import only the first N valid rows")
    parser.add_argument("--no-create-labels", action="store_true")
    parser.add_argument("--no-create-spaces", action="store_true")
    args = parser.parse_args()

    settings = load_settings()
    try:
        table = read_file(args.path, sheet=args.sheet)
        if args.header_row is not None:
            table.set_header_row(args.header_row - 1)
        mapping = suggest_mapping(table.headers())
        if args.name_cols:
            mapping.name_columns = [int(x) - 1 for x in args.name_cols.split(",")]
        if args.phone:
            mapping.phone_column = args.phone - 1
        if args.email:
            mapping.email_column = args.email - 1
        if args.labels:
            mapping.labels_column = args.labels - 1
        if not mapping.is_complete():
            print("The mapping is incomplete. Use --name-cols, --phone, --email, --labels (see validate_file.py).")
            return 1

        result = process_table(table, mapping, NameOptions.from_settings(settings))
        print(f"Rows: {result.total_rows}, valid: {result.valid_count}, rejected: {result.rejected_count}, "
              f"duplicates removed: {result.duplicate_count}")
        rows = result.valid_rows[:args.limit] if args.limit else result.valid_rows
        if not rows:
            print("There are no valid rows to import.")
            return 1

        creds = auth.get_credentials(settings.credentials_path, login_if_needed=False)
        contacts = ContactsService(auth.build_people(creds))
        chat = ChatService(auth.build_chat(creds))
        options = RunOptions(create_labels=not args.no_create_labels, create_spaces=not args.no_create_spaces)
        runner = ImportRunner(
            contacts, chat, options,
            on_progress=lambda done, total: print(f"  [{done}/{total}]"),
            on_log=lambda level, text: print(f"  {level.upper():7} {text}"),
        )

        duplicates = runner.prepare(rows)
        for label, spaces in duplicates:
            chat.choose(label, choose_space(label, spaces))

        labels = {label.casefold() for row in rows for label in row.labels}
        print(f"\nReady to import {len(rows)} rows with {len(labels)} distinct labels.")
        print(f"Create labels: {'on' if options.create_labels else 'off'}, create spaces: {'on' if options.create_spaces else 'off'}")
        if input("This creates real data. Start the import? (y/n): ").strip().lower() != "y":
            print("Cancelled.")
            return 0

        holder = {}
        worker = threading.Thread(target=lambda: holder.setdefault("summary", runner.run(rows)), daemon=True)
        worker.start()
        while worker.is_alive():
            try:
                worker.join(0.2)
            except KeyboardInterrupt:
                print("\nCancelling after the current row...")
                runner.cancel()
        print_summary(holder["summary"])
        return 0

    except RunCancelled as exc:
        print(exc)
        return 0
    except ContactSyncError as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
