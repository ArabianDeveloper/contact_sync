"""Google sign-in: token in AppData, login, delete token, API clients.

The Google libraries are imported inside the functions, so this module can be
imported (and tested) without them.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from app import paths
from app.config import SCOPES
from app.core.errors import AuthError, MissingLibraryError, NotSignedInError

logger = logging.getLogger("contact_sync.auth")

SCOPE_NAMES = {
    "https://www.googleapis.com/auth/spreadsheets.readonly": "Google Sheets (read)",
    "https://www.googleapis.com/auth/contacts": "Google Contacts",
    "https://www.googleapis.com/auth/chat.spaces.readonly": "Google Chat spaces (read)",
    "https://www.googleapis.com/auth/chat.spaces.create": "Google Chat spaces (create)",
    "https://www.googleapis.com/auth/chat.memberships": "Google Chat memberships",
}


# --------------------------------------------------------------------------
# credentials.json
# --------------------------------------------------------------------------

def credentials_file_status(path: str | Path | None) -> tuple[bool, str]:
    """Check the credentials.json file. Returns (ok, message)."""
    if not path or not str(path).strip():
        return False, "No credentials.json file is selected."
    path = Path(path)
    if not path.is_file():
        return False, "The credentials.json file was not found."
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False, "The file is not a valid credentials.json file."
    if not isinstance(data, dict):
        return False, "The file is not a valid credentials.json file."

    if data.get("type") == "service_account":
        return False, "This is a service account key. Create an OAuth client of type 'Desktop app'."
    if "web" in data and "installed" not in data:
        return False, "This is a 'Web application' client. Create an OAuth client of type 'Desktop app'."
    installed = data.get("installed")
    if not isinstance(installed, dict) or not installed.get("client_id") or not installed.get("client_secret"):
        return False, "The file is not an OAuth client of type 'Desktop app'."
    return True, "credentials.json is valid (Desktop app)."


# --------------------------------------------------------------------------
# Token
# --------------------------------------------------------------------------

def token_exists(token_path: str | Path | None = None) -> bool:
    return Path(token_path or paths.token_path()).is_file()


def save_credentials(creds, token_path: str | Path | None = None) -> None:
    path = Path(token_path or paths.token_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(creds.to_json(), encoding="utf-8")
    os.replace(temp, path)


def delete_token(token_path: str | Path | None = None) -> bool:
    """Delete the token file. Returns True if a file was deleted."""
    path = Path(token_path or paths.token_path())
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise AuthError(f"The token file could not be deleted: {exc.strerror or exc}") from exc
    logger.info("Token deleted")
    return True


def load_credentials(token_path: str | Path | None = None):
    """Return valid credentials from the saved token, or None if the user must sign in.

    An expired token is refreshed silently. If the refresh is refused (revoked or expired),
    None is returned. If Google cannot be reached, AuthError is raised (signing in again
    would not help).
    """
    path = Path(token_path or paths.token_path())
    if not path.is_file():
        return None

    try:
        from google.auth.exceptions import RefreshError, TransportError
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except ImportError as exc:
        raise MissingLibraryError("The library 'google-auth' is not installed.") from exc

    try:
        creds = Credentials.from_authorized_user_file(str(path), SCOPES)
    except (ValueError, KeyError, OSError) as exc:
        logger.warning("The token file could not be read (%s)", type(exc).__name__)
        return None

    if creds.valid:
        return creds
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError:
            logger.info("Token refresh was refused, sign-in is needed")
            return None
        except TransportError as exc:
            raise AuthError("Cannot reach Google to refresh the sign-in. Check the internet connection.") from exc
        save_credentials(creds, path)
        return creds
    return None


def login(credentials_path: str | Path, token_path: str | Path | None = None, timeout_seconds: int = 300):
    """Open the browser for Google sign-in and save the token. Blocks until done.

    Run it in a background thread when used from the window.
    """
    ok, message = credentials_file_status(credentials_path)
    if not ok:
        raise AuthError(message)

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise MissingLibraryError("The library 'google-auth-oauthlib' is not installed.") from exc

    # If the user does not allow every permission, do not fail here; the setup check reports it.
    os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

    options = dict(
        port=0,
        prompt="select_account consent",
        authorization_prompt_message="",
        success_message="Contact Sync: sign-in is complete. You can close this window.",
    )
    try:
        flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
        try:
            creds = flow.run_local_server(timeout_seconds=timeout_seconds, **options)
        except TypeError:  # older library without timeout_seconds
            creds = flow.run_local_server(**options)
    except Exception as exc:
        logger.warning("Login failed (%s)", type(exc).__name__)
        raise AuthError("The Google sign-in was not completed. Try again.") from exc

    save_credentials(creds, token_path)
    logger.info("Login completed")
    return creds


def get_credentials(
    credentials_path: str | Path | None,
    token_path: str | Path | None = None,
    login_if_needed: bool = True,
):
    """Saved sign-in if valid, otherwise a new sign-in (when allowed)."""
    creds = load_credentials(token_path)
    if creds is not None:
        return creds
    if not login_if_needed:
        raise NotSignedInError("You are not signed in to Google.")
    if not credentials_path or not str(credentials_path).strip():
        raise AuthError("Select your credentials.json file in the settings first.")
    return login(credentials_path, token_path)


# --------------------------------------------------------------------------
# Scopes
# --------------------------------------------------------------------------

def granted_scopes(creds) -> set[str] | None:
    """The permissions the user really granted, or None if they cannot be found."""
    granted = getattr(creds, "granted_scopes", None)
    if granted:
        return set(granted)

    token = getattr(creds, "token", None)
    if not token:
        return None
    url = "https://oauth2.googleapis.com/tokeninfo?" + urlencode({"access_token": token})
    try:
        with urlopen(url, timeout=10) as response:
            data = json.load(response)
    except Exception as exc:
        logger.info("Granted scopes could not be checked (%s)", type(exc).__name__)
        return None
    scope = data.get("scope") if isinstance(data, dict) else None
    return set(scope.split()) if isinstance(scope, str) else None


def missing_scopes(creds) -> list[str] | None:
    """Names of the required permissions that were not granted (None if unknown)."""
    granted = granted_scopes(creds)
    if granted is None:
        return None
    return [SCOPE_NAMES[scope] for scope in SCOPES if scope not in granted]


# --------------------------------------------------------------------------
# API clients
# --------------------------------------------------------------------------

def build_service(name: str, version: str, creds):
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise MissingLibraryError("The library 'google-api-python-client' is not installed.") from exc
    return build(name, version, credentials=creds, cache_discovery=False)


def build_people(creds):
    return build_service("people", "v1", creds)


def build_chat(creds):
    return build_service("chat", "v1", creds)


def build_sheets(creds):
    return build_service("sheets", "v4", creds)
