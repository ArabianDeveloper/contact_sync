"""Stage 4 test tool: tries the Google Contacts and Chat code on your real account.

Usage (sign in first with google_check.py login):
    python google_try.py labels
    python google_try.py contacts
    python google_try.py spaces
    python google_try.py add --name "Test Person" --phone 99123456 --email someone@yourdomain.com --labels "Test1,Test2"

'add' CREATES real data (a contact, labels, spaces, space members) after you confirm.
Use a test person, a test label and a test space name. Options: --no-create-labels, --no-create-spaces
"""
from __future__ import annotations

import argparse
import sys

from app.core.cleaning import is_valid_email, parse_phone, split_labels
from app.core.errors import ContactSyncError
from app.services import auth
from app.services.chat import ChatService, DuplicateSpaceError
from app.services.contacts import ContactsService
from app.services.errors import describe_error
from app.settings import load_settings


def step(text: str, action):
    """Run one step. Prints the result. Returns (ok, value)."""
    try:
        value = action()
        print(f"  [ OK ] {text}" + (f": {value}" if isinstance(value, (str, int)) and value else ""))
        return True, value
    except Exception as exc:
        info = describe_error(exc) if not isinstance(exc, ContactSyncError) else None
        print(f"  [FAIL] {text}: {info.message if info else exc}")
        return False, None


def choose_space(label, spaces) -> str | None:
    print(f"\nMore than one space is named '{label}':")
    for index, space in enumerate(spaces, start=1):
        print(f"  {index}. {space.name}  created: {space.create_time or '-'}  members: {space.member_count or '-'}")
    print("  0. skip this space")
    while True:
        answer = input("Choose a number: ").strip()
        if answer == "0":
            return None
        if answer.isdigit() and 1 <= int(answer) <= len(spaces):
            return spaces[int(answer) - 1].name


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Try the Google Contacts and Chat code.")
    parser.add_argument("command", choices=["labels", "contacts", "spaces", "add"])
    parser.add_argument("--name")
    parser.add_argument("--phone")
    parser.add_argument("--email")
    parser.add_argument("--labels")
    parser.add_argument("--no-create-labels", action="store_true")
    parser.add_argument("--no-create-spaces", action="store_true")
    args = parser.parse_args()

    settings = load_settings()
    try:
        creds = auth.get_credentials(settings.credentials_path, login_if_needed=False)
        contacts = ContactsService(auth.build_people(creds))
        chat = ChatService(auth.build_chat(creds))

        if args.command == "labels":
            print(f"Labels: {contacts.load_labels()}")
            return 0
        if args.command == "contacts":
            read = contacts.load_contacts(lambda n: print(f"  read {n} contacts..."))
            print(f"Contacts read: {read}")
            return 0
        if args.command == "spaces":
            print(f"Spaces you belong to: {chat.load_spaces()}")
            return 0
    except ContactSyncError as exc:
        print(f"ERROR: {exc}")
        return 1
    except Exception as exc:
        print(f"ERROR: {describe_error(exc).message}")
        return 1

    # ---- add: one full row, like the real import will do ----
    phone = parse_phone(args.phone or "")
    labels = split_labels(args.labels or "")
    if not (args.name and args.name.strip() and phone and args.email and is_valid_email(args.email) and labels):
        print("ERROR: --name, --phone (valid), --email (valid) and --labels are required.")
        return 1

    print(f"\nThis will create real data: contact '{args.name}' ({phone}), labels {labels}, "
          f"spaces with the same names, and add {args.email} to them.")
    if input("Continue? (y/n): ").strip().lower() != "y":
        print("Cancelled.")
        return 0

    create_labels, create_spaces = not args.no_create_labels, not args.no_create_spaces
    print("\nLoading...")
    ok1, _ = step("Labels loaded", lambda: contacts.load_labels())
    ok2, _ = step("Contacts loaded", lambda: contacts.load_contacts())
    ok3, _ = step("Spaces loaded", lambda: chat.load_spaces())
    if not (ok1 and ok2 and ok3):
        return 1

    for label, spaces in chat.duplicate_names(labels):
        chat.choose(label, choose_space(label, spaces))

    print("\nContact:")
    contact = contacts.find(phone)
    if contact:
        print(f"  [ OK ] already exists ({contact.resource_name}), it is not created again")
    else:
        ok, contact = step("created", lambda: contacts.create_contact(args.name.strip(), phone, args.email.strip()))
        if not ok:
            return 1

    for label in labels:
        print(f"\nLabel '{label}':")
        try:
            ref = contacts.ensure_label(label, create_labels)
        except Exception as exc:
            print(f"  [FAIL] label: {describe_error(exc).message}")
            ref = None
        else:
            if ref is None:
                print("  [REPORTED] label does not exist and auto-create is off")
            else:
                print(f"  [ OK ] label: {'created' if ref.created else 'found'}")
                step("added to label", lambda: contacts.add_to_label(contact, ref.resource_name))

        try:
            space = chat.ensure_space(label, create_spaces)
        except DuplicateSpaceError as exc:
            print(f"  [FAIL] space: {exc}")
            continue
        except Exception as exc:
            print(f"  [FAIL] space: {describe_error(exc).message}")
            continue
        if space is None:
            print("  [REPORTED] space does not exist (or skipped) and was not created")
            continue
        print(f"  [ OK ] space: {'created' if space.created else 'found'} ({space.name})")
        step("added to space", lambda: chat.add_member(space.name, args.email.strip()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
