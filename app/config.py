"""Application constants."""
from __future__ import annotations

APP_NAME = "Contact Sync"
APP_DIR_NAME = "ContactSync"
VERSION = "1.0.0"

# "owner/name" of the public GitHub repository, used by the update check (stage 8).
GITHUB_REPO: str | None = "ArabianDeveloper/contact_sync"

DEFAULT_REGION = "OM"      # Oman (+968)
PREVIEW_ROWS = 100         # rows shown in the preview table
HEADER_SCAN_ROWS = 20      # rows examined when guessing the header row

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/contacts",
    "https://www.googleapis.com/auth/chat.spaces.readonly",
    "https://www.googleapis.com/auth/chat.spaces.create",
    "https://www.googleapis.com/auth/chat.memberships",
]
