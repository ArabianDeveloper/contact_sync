"""Errors with messages that can be shown to the user."""
from __future__ import annotations


class ContactSyncError(Exception):
    """Base class. The message is readable by the user."""


class UnsupportedFileError(ContactSyncError):
    """The file type is not supported or cannot be detected."""


class ReadError(ContactSyncError):
    """The file was detected but could not be read."""


class MissingLibraryError(ContactSyncError):
    """A required library is not installed."""


class AuthError(ContactSyncError):
    """Google sign-in problem."""


class NotSignedInError(AuthError):
    """There is no valid Google sign-in."""
