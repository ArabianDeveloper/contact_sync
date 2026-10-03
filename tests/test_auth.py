import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.config import SCOPES
from app.core.errors import AuthError, MissingLibraryError, NotSignedInError
from app.services import auth
from tests.fakes import fake_google_modules

INSTALLED = {"installed": {"client_id": "id", "client_secret": "secret", "redirect_uris": ["http://localhost"]}}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.token = self.dir / "token.json"
        self.credentials = self.dir / "credentials.json"
        self.credentials.write_text(json.dumps(INSTALLED), encoding="utf-8")
        self.modules, self.g = fake_google_modules()
        patcher = mock.patch.dict(sys.modules, self.modules)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write_token(self, **data):
        self.token.write_text(json.dumps(data), encoding="utf-8")


class CredentialsFileTests(Base):
    def status(self, content=None, path=None):
        if content is not None:
            self.credentials.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
        return auth.credentials_file_status(path or self.credentials)

    def test_valid(self):
        self.assertTrue(self.status()[0])

    def test_problems(self):
        self.assertFalse(auth.credentials_file_status(None)[0])
        self.assertFalse(auth.credentials_file_status("  ")[0])
        self.assertFalse(auth.credentials_file_status(self.dir / "missing.json")[0])
        self.assertFalse(self.status("{not json")[0])
        self.assertFalse(self.status([1, 2])[0])
        ok, message = self.status({"web": {"client_id": "a", "client_secret": "b"}})
        self.assertFalse(ok)
        self.assertIn("Desktop app", message)
        self.assertFalse(self.status({"type": "service_account"})[0])
        self.assertFalse(self.status({"installed": {"client_id": "a"}})[0])


class TokenTests(Base):
    def test_no_token(self):
        self.assertIsNone(auth.load_credentials(self.token))

    def test_valid_token(self):
        self.write_token(token="abc", valid=True)
        creds = auth.load_credentials(self.token)
        self.assertEqual(creds.token, "abc")

    def test_expired_token_is_refreshed_and_saved(self):
        self.write_token(token="old", valid=False, expired=True, refresh_token="r")
        creds = auth.load_credentials(self.token)
        self.assertEqual(creds.token, "refreshed")
        self.assertEqual(json.loads(self.token.read_text())["token"], "refreshed")

    def test_refresh_refused_means_sign_in_needed(self):
        self.write_token(token="old", valid=False, expired=True, refresh_token="r")
        self.g.Credentials.refresh_effect = self.g.RefreshError("invalid_grant")
        self.assertIsNone(auth.load_credentials(self.token))

    def test_network_problem_is_an_error_not_a_sign_in_request(self):
        self.write_token(token="old", valid=False, expired=True, refresh_token="r")
        self.g.Credentials.refresh_effect = self.g.TransportError("offline")
        with self.assertRaises(AuthError):
            auth.load_credentials(self.token)

    def test_expired_without_refresh_token(self):
        self.write_token(token="old", valid=False, expired=True, refresh_token=None)
        self.assertIsNone(auth.load_credentials(self.token))

    def test_corrupt_token(self):
        self.token.write_text("{broken", encoding="utf-8")
        self.assertIsNone(auth.load_credentials(self.token))

    def test_delete_token(self):
        self.write_token(token="abc")
        self.assertTrue(auth.token_exists(self.token))
        self.assertTrue(auth.delete_token(self.token))
        self.assertFalse(auth.token_exists(self.token))
        self.assertFalse(auth.delete_token(self.token))

    def test_default_location_is_appdata(self):
        with mock.patch.dict(os.environ, {"APPDATA": str(self.dir)}):
            self.assertFalse(auth.token_exists())
            self.assertEqual(auth.delete_token(), False)
            from app import paths
            self.assertEqual(paths.token_path(), self.dir / "ContactSync" / "token.json")


class LoginTests(Base):
    def test_login_saves_the_token_with_the_right_options(self):
        creds = auth.login(self.credentials, self.token)
        self.assertEqual(creds.token, "login-token")
        self.assertEqual(json.loads(self.token.read_text())["token"], "login-token")
        call = self.g.Flow.calls[0]
        self.assertEqual(call["prompt"], "select_account consent")
        self.assertEqual(call["port"], 0)
        self.assertEqual(call["timeout_seconds"], 300)

    def test_login_failure_is_a_readable_error(self):
        self.g.Flow.effect = RuntimeError("browser closed")
        with self.assertRaises(AuthError):
            auth.login(self.credentials, self.token)
        self.assertFalse(self.token.exists())

    def test_invalid_credentials_file_is_checked_first(self):
        self.credentials.write_text("{}", encoding="utf-8")
        with self.assertRaises(AuthError):
            auth.login(self.credentials, self.token)
        self.assertEqual(self.g.Flow.calls, [])

    def test_missing_library(self):
        with mock.patch.dict(sys.modules, {"google_auth_oauthlib.flow": None}):
            with self.assertRaises(MissingLibraryError):
                auth.login(self.credentials, self.token)


class GetCredentialsTests(Base):
    def test_uses_the_saved_token_without_login(self):
        self.write_token(token="abc", valid=True)
        self.assertEqual(auth.get_credentials(self.credentials, self.token).token, "abc")
        self.assertEqual(self.g.Flow.calls, [])

    def test_not_signed_in_when_login_is_not_allowed(self):
        with self.assertRaises(NotSignedInError):
            auth.get_credentials(self.credentials, self.token, login_if_needed=False)

    def test_needs_the_credentials_path_to_login(self):
        with self.assertRaises(AuthError):
            auth.get_credentials(None, self.token)

    def test_logs_in_when_there_is_no_token(self):
        self.assertEqual(auth.get_credentials(self.credentials, self.token).token, "login-token")
        self.assertTrue(self.token.exists())


class ScopesTests(Base):
    def test_granted_scopes_from_the_credentials(self):
        creds = self.g.Credentials(granted_scopes=SCOPES[:2])
        self.assertEqual(auth.granted_scopes(creds), set(SCOPES[:2]))
        missing = auth.missing_scopes(creds)
        self.assertEqual(len(missing), 3)
        self.assertIn("Google Chat memberships", missing)

    def test_all_granted(self):
        self.assertEqual(auth.missing_scopes(self.g.Credentials(granted_scopes=list(SCOPES))), [])

    def test_tokeninfo_is_used_when_scopes_are_not_in_the_credentials(self):
        creds = self.g.Credentials(token="abc", granted_scopes=None)
        body = json.dumps({"scope": " ".join(SCOPES)}).encode()
        with mock.patch.object(auth, "urlopen", return_value=io.BytesIO(body)):
            self.assertEqual(auth.missing_scopes(creds), [])

    def test_unknown_when_tokeninfo_fails(self):
        creds = self.g.Credentials(token="abc", granted_scopes=None)
        with mock.patch.object(auth, "urlopen", side_effect=OSError("offline")):
            self.assertIsNone(auth.missing_scopes(creds))
        self.assertIsNone(auth.granted_scopes(self.g.Credentials(token=None, granted_scopes=None)))


if __name__ == "__main__":
    unittest.main()
