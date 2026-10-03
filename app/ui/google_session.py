"""The Google sign-in used by the window. No Qt code, so it can be tested.

The sign-in is requested the first time Google is needed (loading a Google Sheet, running the
setup check, starting an import). It is kept in memory until the token is deleted.
"""
from __future__ import annotations

from typing import Callable

from app.core.readers.sheet_reader import read_sheet
from app.services import auth
from app.services.chat import ChatService
from app.services.contacts import ContactsService


class GoogleSession:
    def __init__(self, credentials_path: Callable[[], str | None], token_path=None):
        self._credentials_path = credentials_path
        self._token_path = token_path
        self._creds = None

    def reset(self) -> None:
        """Forget the sign-in in memory (after the token is deleted)."""
        self._creds = None

    def current_credentials(self):
        """The saved sign-in if it is valid, otherwise None. Never opens the browser."""
        if self._creds is None:
            self._creds = auth.load_credentials(self._token_path)
        return self._creds

    def credentials(self, login: bool = True):
        """The sign-in. If there is none and `login` is True, the browser opens. Blocks until
        done, so call it from a background thread."""
        if self._creds is None:
            self._creds = auth.get_credentials(self._credentials_path(), self._token_path, login_if_needed=login)
        return self._creds

    def build_services(self) -> tuple[ContactsService, ChatService]:
        creds = self.credentials(login=True)
        return ContactsService(auth.build_people(creds)), ChatService(auth.build_chat(creds))


def read_google_sheet(session: GoogleSession, text: str, sheet: str | None = None, cell_range: str | None = None):
    """Read a Google Sheet (link or ID). Called from a background thread."""
    service = auth.build_sheets(session.credentials(login=True))
    return read_sheet(service, text, sheet, cell_range)
