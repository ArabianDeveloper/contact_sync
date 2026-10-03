"""Stage 3 test tool: Google sign-in and setup check.

Usage:
    python google_check.py status
    python google_check.py login --credentials "C:\path\credentials.json"
    python google_check.py check
    python google_check.py delete-token

--credentials saves the path in the settings (it is remembered for the next runs).
"""
from __future__ import annotations

import argparse
import sys

from app import paths
from app.core.errors import ContactSyncError
from app.settings import load_settings, save_settings
from app.services import auth
from app.services.setup_check import run_setup_check

_MARK = {"ok": "[ OK ]", "fail": "[FAIL]", "warn": "[WARN]", "skipped": "[SKIP]"}


def print_results(results) -> bool:
    all_ok = True
    for result in results:
        print(f"{_MARK[result.status]} {result.title}: {result.message}")
        if result.help_url:
            print(f"        Link: {result.help_url}")
        if result.status in ("fail", "warn"):
            all_ok = False
    return all_ok


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Google sign-in and setup check.")
    parser.add_argument("command", choices=["status", "login", "check", "delete-token"])
    parser.add_argument("--credentials", default=None, help="path of credentials.json (saved in the settings)")
    args = parser.parse_args()

    settings = load_settings()
    if args.credentials:
        settings.credentials_path = args.credentials
        save_settings(settings)
        print(f"credentials.json path saved: {args.credentials}")

    try:
        if args.command == "status":
            ok, message = auth.credentials_file_status(settings.credentials_path)
            print(f"credentials.json: {message}")
            print(f"Token file      : {paths.token_path()} ({'exists' if auth.token_exists() else 'not found'})")
            creds = auth.load_credentials()
            print(f"Signed in       : {'yes' if creds else 'no'}")
            return 0

        if args.command == "login":
            print("A browser window will open. Sign in and allow every permission.")
            creds = auth.get_credentials(settings.credentials_path)
            print("Signed in. Running the setup check...\n")
            return 0 if print_results(run_setup_check(settings.credentials_path, creds)) else 1

        if args.command == "check":
            creds = auth.load_credentials()
            return 0 if print_results(run_setup_check(settings.credentials_path, creds)) else 1

        if args.command == "delete-token":
            if not auth.token_exists():
                print("There is no token file.")
                return 0
            if input("Delete the token? You will have to sign in again. (y/n): ").strip().lower() != "y":
                print("Cancelled.")
                return 0
            auth.delete_token()
            print("Token deleted.")
            return 0
    except ContactSyncError as exc:
        print(f"ERROR: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
