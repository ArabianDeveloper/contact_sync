"""Google Sheets: read a sheet (Sheets API v4)."""
from __future__ import annotations

import re

from app.core.errors import ContactSyncError
from app.services.errors import BAD_REQUEST, NOT_FOUND, PERMISSION, describe_error

_URL_ID = re.compile(r"/spreadsheets/d/([A-Za-z0-9_-]+)")
_BARE_ID = re.compile(r"^[A-Za-z0-9_-]{20,}$")


def parse_sheet_id(text: str) -> str | None:
    """The spreadsheet ID from a link or from the ID itself, or None."""
    text = (text or "").strip()
    match = _URL_ID.search(text)
    if match:
        return match.group(1)
    return text if _BARE_ID.match(text) else None


def quote_tab(title: str) -> str:
    """A tab name as used in a range: 'My tab'"""
    return "'" + title.replace("'", "''") + "'"


def read_error(exc: Exception, with_range: bool = False) -> ContactSyncError:
    """A readable error for a failure while reading a spreadsheet."""
    if isinstance(exc, ContactSyncError):
        return exc
    info = describe_error(exc)
    if info.kind == NOT_FOUND:
        return ContactSyncError("The spreadsheet was not found. Check the link, and that your Google account can open it.")
    if info.kind == PERMISSION:
        return ContactSyncError("Your Google account has no access to this spreadsheet.")
    if info.kind == BAD_REQUEST and with_range:
        return ContactSyncError("The range is not valid. Use a range such as A1:F200.")
    return ContactSyncError(info.message)


def list_tabs(service, spreadsheet_id: str) -> list[str]:
    response = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id, fields="sheets.properties.title"
    ).execute()
    return [
        s["properties"]["title"] for s in response.get("sheets", [])
        if isinstance(s.get("properties"), dict) and "title" in s["properties"]
    ]


def read_values(service, spreadsheet_id: str, tab: str, cell_range: str | None = None) -> list[list]:
    """The cell values of a tab, as shown in the sheet. Without a range the whole tab is read."""
    target = quote_tab(tab) + (f"!{cell_range}" if cell_range else "")
    response = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range=target, valueRenderOption="FORMATTED_VALUE"
    ).execute()
    return response.get("values", [])
