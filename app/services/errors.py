"""Converts Google errors into a kind and a readable message.

Works with the errors of googleapiclient (HttpError), google-auth and the network
without importing those libraries, so it can be tested alone.
"""
from __future__ import annotations

import json
import socket
import ssl
from dataclasses import dataclass

# Kinds
API_DISABLED = "api_disabled"
INSUFFICIENT_SCOPE = "insufficient_scope"
AUTH = "auth"
PERMISSION = "permission"
QUOTA = "quota"
SERVER = "server"
NOT_FOUND = "not_found"
ALREADY_EXISTS = "already_exists"
BAD_REQUEST = "bad_request"
NETWORK = "network"
OTHER = "other"

_FATAL_KINDS = {API_DISABLED, INSUFFICIENT_SCOPE, AUTH}

_SERVICE_NAMES = {
    "people.googleapis.com": "People API (Google Contacts)",
    "chat.googleapis.com": "Google Chat API",
    "sheets.googleapis.com": "Google Sheets API",
}

_QUOTA_REASONS = {"rateLimitExceeded", "userRateLimitExceeded", "quotaExceeded", "dailyLimitExceeded",
                  "RATE_LIMIT_EXCEEDED", "RESOURCE_EXHAUSTED"}
_NETWORK_CLASS_NAMES = {"ServerNotFoundError", "TransportError", "ConnectTimeout", "ReadTimeout"}


@dataclass
class GoogleError:
    kind: str
    message: str                   # readable, can be shown to the user
    status: int | None = None      # HTTP status
    reason: str | None = None      # Google error reason
    service: str | None = None     # friendly API name (for api_disabled)
    help_url: str | None = None    # activation link when Google gives one

    @property
    def is_fatal(self) -> bool:
        """True when the whole run must stop (not only the current item)."""
        return self.kind in _FATAL_KINDS


def _class_names(exc: BaseException) -> set[str]:
    return {cls.__name__ for cls in type(exc).__mro__}


def _parse_http_error(exc: BaseException) -> dict | None:
    """Return {status, message, rpc_status, reason, service, help_url} for an HttpError-like
    exception, or None if it is not one."""
    response = getattr(exc, "resp", None)
    status = getattr(response, "status", None)
    if status is None:
        return None
    try:
        status = int(status)
    except (TypeError, ValueError):
        return None

    content = getattr(exc, "content", b"")
    try:
        text = content.decode("utf-8", "replace") if isinstance(content, (bytes, bytearray)) else str(content)
        data = json.loads(text)
    except ValueError:
        data = {}
    error = data.get("error", {}) if isinstance(data, dict) else {}
    if not isinstance(error, dict):
        error = {}

    reason = service = help_url = None
    for detail in error.get("details") or []:
        if not isinstance(detail, dict):
            continue
        reason = reason or detail.get("reason")
        metadata = detail.get("metadata")
        if isinstance(metadata, dict):
            service = service or metadata.get("service")
        for link in detail.get("links") or []:
            if isinstance(link, dict) and link.get("url"):
                help_url = help_url or link["url"]
    for item in error.get("errors") or []:
        if isinstance(item, dict):
            reason = reason or item.get("reason")

    return {
        "status": status,
        "message": error.get("message") or "",
        "rpc_status": error.get("status"),
        "reason": reason,
        "service": service,
        "help_url": help_url,
    }


def describe_error(exc: BaseException) -> GoogleError:
    """Classify any exception raised while talking to Google."""
    info = _parse_http_error(exc)
    if info is not None:
        return _describe_http(info)

    names = _class_names(exc)
    if "RefreshError" in names:
        return GoogleError(AUTH, "The Google sign-in has expired or was revoked. Sign in again.")
    if isinstance(exc, (ConnectionError, TimeoutError, socket.gaierror, socket.timeout, ssl.SSLError)) \
            or names & _NETWORK_CLASS_NAMES:
        return GoogleError(NETWORK, "Cannot reach Google. Check the internet connection.")
    return GoogleError(OTHER, str(exc) or type(exc).__name__)


def _describe_http(info: dict) -> GoogleError:
    status, message, rpc = info["status"], info["message"], info["rpc_status"]
    reason, service, help_url = info["reason"], info["service"], info["help_url"]
    lowered = message.lower()
    common = dict(status=status, reason=reason, help_url=help_url)

    if reason in ("SERVICE_DISABLED", "accessNotConfigured") or "has not been used in project" in lowered \
            or "api is not enabled" in lowered:
        name = _SERVICE_NAMES.get(service or "", None)
        label = name or "A required Google API"
        text = (f"{label} is not enabled in your Google Cloud project. "
                "Enable it in the Google Cloud Console (APIs & Services > Library), then try again.")
        return GoogleError(API_DISABLED, text, service=name, **common)

    if reason in ("ACCESS_TOKEN_SCOPE_INSUFFICIENT", "insufficientPermissions") \
            or "insufficient authentication scopes" in lowered:
        return GoogleError(
            INSUFFICIENT_SCOPE,
            "The Google sign-in does not have all the required permissions. "
            "Delete the token in the settings and sign in again, and allow every permission.",
            **common,
        )

    if status == 401 or rpc == "UNAUTHENTICATED":
        return GoogleError(AUTH, "The Google sign-in is not valid. Sign in again.", **common)
    if status == 429 or rpc == "RESOURCE_EXHAUSTED" or reason in _QUOTA_REASONS:
        return GoogleError(QUOTA, "Google quota or rate limit reached." + _tail(message), **common)
    if status == 403:
        return GoogleError(PERMISSION, "Google denied the request." + _tail(message), **common)
    if status == 404:
        return GoogleError(NOT_FOUND, "Not found." + _tail(message), **common)
    if status == 409 or rpc == "ALREADY_EXISTS":
        return GoogleError(ALREADY_EXISTS, "Already exists." + _tail(message), **common)
    if status == 400:
        return GoogleError(BAD_REQUEST, "Google rejected the request." + _tail(message), **common)
    if status >= 500:
        return GoogleError(SERVER, f"Google server error ({status})." + _tail(message), **common)
    return GoogleError(OTHER, f"Google error ({status})." + _tail(message), **common)


def _tail(message: str) -> str:
    message = " ".join(message.split())
    return f" {message}" if message else ""
