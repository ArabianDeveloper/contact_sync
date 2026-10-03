"""Setup check (item 43): is everything ready to use Google?"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

from app.core.errors import ContactSyncError
from app.services import auth
from app.services.errors import BAD_REQUEST, NOT_FOUND, PERMISSION, describe_error

logger = logging.getLogger("contact_sync.setup_check")

OK, FAIL, WARN, SKIPPED = "ok", "fail", "warn", "skipped"

_SHEETS_TEST_ID = "contact-sync-setup-check"


@dataclass
class CheckResult:
    key: str
    title: str
    status: str            # ok, fail, warn, skipped
    message: str
    help_url: str | None = None


def _default_builders() -> dict[str, Callable]:
    return {"people": auth.build_people, "chat": auth.build_chat, "sheets": auth.build_sheets}


def _call_people(service):
    service.contactGroups().list(pageSize=1).execute()


def _call_chat(service):
    service.spaces().list(pageSize=1).execute()


def _call_sheets(service):
    service.spreadsheets().get(spreadsheetId=_SHEETS_TEST_ID, fields="spreadsheetId").execute()


_API_CHECKS = (
    ("people", "People API (Google Contacts)", _call_people),
    ("chat", "Google Chat API", _call_chat),
    ("sheets", "Google Sheets API", _call_sheets),
)


def run_setup_check(
    credentials_path: str | None,
    creds,
    builders: dict[str, Callable] | None = None,
) -> list[CheckResult]:
    """Run all checks. `creds` is the current sign-in, or None if the user is not signed in.

    The function never raises for Google errors; every problem becomes a result line.
    """
    builders = builders or _default_builders()
    results: list[CheckResult] = []

    ok, message = auth.credentials_file_status(credentials_path)
    results.append(CheckResult("credentials", "credentials.json", OK if ok else FAIL, message))

    if creds is None:
        results.append(CheckResult("login", "Google sign-in", FAIL, "You are not signed in. Sign in first."))
        results.append(CheckResult("scopes", "Permissions", SKIPPED, "Skipped: sign in first."))
        for key, title, _call in _API_CHECKS:
            results.append(CheckResult(key, title, SKIPPED, "Skipped: sign in first."))
        return results

    results.append(CheckResult("login", "Google sign-in", OK, "Signed in."))
    results.append(_check_scopes(creds))

    for key, title, call in _API_CHECKS:
        results.append(_check_api(key, title, call, builders, creds))

    logger.info("Setup check: %s", ", ".join(f"{r.key}={r.status}" for r in results))
    return results


def _check_scopes(creds) -> CheckResult:
    try:
        missing = auth.missing_scopes(creds)
    except Exception as exc:  # the check must not stop the others
        logger.warning("Scope check failed (%s)", type(exc).__name__)
        missing = None
    if missing is None:
        return CheckResult("scopes", "Permissions", WARN,
                           "The granted permissions could not be verified. The API checks below will show any problem.")
    if missing:
        return CheckResult("scopes", "Permissions", FAIL,
                           "Missing permissions: " + ", ".join(missing) +
                           ". Delete the token and sign in again, and allow every permission.")
    return CheckResult("scopes", "Permissions", OK, "All required permissions are granted.")


def _check_api(key: str, title: str, call: Callable, builders: dict[str, Callable], creds) -> CheckResult:
    try:
        service = builders[key](creds)
        call(service)
    except ContactSyncError as exc:
        return CheckResult(key, title, FAIL, str(exc))
    except Exception as exc:
        info = describe_error(exc)
        # For Sheets a test ID that does not exist is expected: any answer other than
        # "API disabled" or a sign-in problem means the API is enabled.
        if key == "sheets" and info.kind in (NOT_FOUND, BAD_REQUEST, PERMISSION):
            return CheckResult(key, title, OK, f"{title} is enabled.")
        return CheckResult(key, title, FAIL, info.message, info.help_url)
    return CheckResult(key, title, OK, f"{title} is enabled.")
