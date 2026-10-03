"""Small fake versions of 'phonenumbers' and 'email_validator'.

They are used only to test the program's own code when the real libraries are not
installed. They are NOT used when the real libraries are installed and tested
(see the 'Real library' test classes).
"""
import re
import sys
import types
from unittest import mock


def fake_phonenumbers():
    module = types.ModuleType("phonenumbers")

    class NumberParseException(Exception):
        pass

    class PhoneNumberFormat:
        E164 = 0

    class Number:
        def __init__(self, e164, national_ok):
            self.e164 = e164
            self.ok = national_ok

    def parse(text, region):
        if not re.match(r"^\+?\d+$", text):
            raise NumberParseException("not a number")
        if text.startswith("+"):
            return Number(text, re.match(r"^\+\d{10,14}$", text) is not None)
        digits = text
        if digits.startswith("968") and len(digits) == 11:
            digits = digits[3:]
        return Number("+968" + digits, re.match(r"^[79]\d{7}$", digits) is not None)

    module.NumberParseException = NumberParseException
    module.PhoneNumberFormat = PhoneNumberFormat
    module.parse = parse
    module.is_valid_number = lambda number: number.ok
    module.format_number = lambda number, fmt: number.e164
    return module


def fake_email_validator():
    module = types.ModuleType("email_validator")

    class EmailNotValidError(Exception):
        pass

    def validate_email(text, check_deliverability=True):
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", text):
            raise EmailNotValidError("invalid")
        return object()

    module.EmailNotValidError = EmailNotValidError
    module.validate_email = validate_email
    return module


def patch_fake_libraries():
    """Return a started patcher; call .stop() (or use addCleanup) to remove it."""
    patcher = mock.patch.dict(sys.modules, {
        "phonenumbers": fake_phonenumbers(),
        "email_validator": fake_email_validator(),
    })
    patcher.start()
    return patcher


def real_libraries_available():
    try:
        import email_validator  # noqa: F401
        import phonenumbers  # noqa: F401
        return True
    except ImportError:
        return False


def fake_google_modules():
    """Fake google-auth and google-auth-oauthlib modules (new classes on every call).

    Returns (modules, ns). Use mock.patch.dict(sys.modules, modules).
    """
    import json
    from pathlib import Path

    class RefreshError(Exception):
        pass

    class TransportError(Exception):
        pass

    class FakeCredentials:
        refresh_effect = None

        def __init__(self, token="tok", valid=True, expired=False, refresh_token="ref", granted_scopes=None):
            self.token = token
            self.valid = valid
            self.expired = expired
            self.refresh_token = refresh_token
            self.granted_scopes = granted_scopes

        @classmethod
        def from_authorized_user_file(cls, path, scopes=None):
            return cls(**json.loads(Path(path).read_text(encoding="utf-8")))

        def to_json(self):
            return json.dumps({
                "token": self.token, "valid": self.valid, "expired": self.expired,
                "refresh_token": self.refresh_token, "granted_scopes": self.granted_scopes,
            })

        def refresh(self, request):
            if FakeCredentials.refresh_effect is not None:
                raise FakeCredentials.refresh_effect
            self.token, self.valid, self.expired = "refreshed", True, False

    class InstalledAppFlow:
        calls = []
        effect = None
        scopes = None

        @classmethod
        def from_client_secrets_file(cls, path, scopes):
            flow = cls()
            flow.path, flow.scopes = path, scopes
            return flow

        def run_local_server(self, **kwargs):
            InstalledAppFlow.calls.append(kwargs)
            if InstalledAppFlow.effect is not None:
                raise InstalledAppFlow.effect
            return FakeCredentials(token="login-token", granted_scopes=list(self.scopes))

    def module(name, **attrs):
        mod = types.ModuleType(name)
        for key, value in attrs.items():
            setattr(mod, key, value)
        return mod

    modules = {
        "google": module("google"),
        "google.oauth2": module("google.oauth2"),
        "google.oauth2.credentials": module("google.oauth2.credentials", Credentials=FakeCredentials),
        "google.auth": module("google.auth"),
        "google.auth.transport": module("google.auth.transport"),
        "google.auth.transport.requests": module("google.auth.transport.requests", Request=object),
        "google.auth.exceptions": module("google.auth.exceptions", RefreshError=RefreshError,
                                         TransportError=TransportError),
        "google_auth_oauthlib": module("google_auth_oauthlib"),
        "google_auth_oauthlib.flow": module("google_auth_oauthlib.flow", InstalledAppFlow=InstalledAppFlow),
    }
    ns = types.SimpleNamespace(
        RefreshError=RefreshError, TransportError=TransportError,
        Credentials=FakeCredentials, Flow=InstalledAppFlow,
    )
    return modules, ns


class FakeHttpError(Exception):
    """Looks like googleapiclient.errors.HttpError (resp.status and content)."""

    def __init__(self, status, body=None):
        import json
        super().__init__(f"HttpError {status}")
        self.resp = types.SimpleNamespace(status=status)
        self.content = body if isinstance(body, bytes) else json.dumps(body or {}).encode("utf-8")
