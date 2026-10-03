import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from app.config import SCOPES
from app.services import setup_check as sc
from tests.fakes import FakeHttpError
from tests.test_auth import INSTALLED


class FakeService:
    """Records calls; raises the given error when execute() runs."""

    def __init__(self, error=None):
        self.error = error

    def _exec(self):
        return SimpleNamespace(execute=self._execute)

    def _execute(self):
        if self.error:
            raise self.error
        return {}

    def contactGroups(self):
        return SimpleNamespace(list=lambda **kw: self._exec())

    def spaces(self):
        return SimpleNamespace(list=lambda **kw: self._exec())

    def spreadsheets(self):
        return SimpleNamespace(get=lambda **kw: self._exec())


DISABLED = FakeHttpError(403, {"error": {"message": "disabled", "details": [
    {"reason": "SERVICE_DISABLED", "metadata": {"service": "chat.googleapis.com"}},
    {"links": [{"url": "https://console.example/enable"}]}]}})


class SetupCheckTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.credentials = Path(tmp.name) / "credentials.json"
        self.credentials.write_text(json.dumps(INSTALLED), encoding="utf-8")
        self.creds = SimpleNamespace(granted_scopes=list(SCOPES), token="t")

    def run_check(self, creds="default", **errors):
        creds = self.creds if creds == "default" else creds
        builders = {key: (lambda c, key=key: FakeService(errors.get(key))) for key in ("people", "chat", "sheets")}
        results = sc.run_setup_check(str(self.credentials), creds, builders)
        return {r.key: r for r in results}

    def test_everything_ok(self):
        results = self.run_check(sheets=FakeHttpError(404, {"error": {"message": "Requested entity was not found."}}))
        self.assertEqual(list(results), ["credentials", "login", "scopes", "people", "chat", "sheets"])
        self.assertTrue(all(r.status == sc.OK for r in results.values()))

    def test_disabled_chat_api(self):
        results = self.run_check(chat=DISABLED)
        self.assertEqual(results["chat"].status, sc.FAIL)
        self.assertIn("not enabled", results["chat"].message)
        self.assertEqual(results["chat"].help_url, "https://console.example/enable")
        self.assertEqual(results["people"].status, sc.OK)

    def test_disabled_sheets_api_is_a_failure_but_404_is_ok(self):
        disabled = FakeHttpError(403, {"error": {"message": "x", "details": [
            {"reason": "SERVICE_DISABLED", "metadata": {"service": "sheets.googleapis.com"}}]}})
        self.assertEqual(self.run_check(sheets=disabled)["sheets"].status, sc.FAIL)
        self.assertEqual(self.run_check(sheets=FakeHttpError(404))["sheets"].status, sc.OK)
        self.assertEqual(self.run_check(sheets=FakeHttpError(401))["sheets"].status, sc.FAIL)

    def test_not_signed_in_skips_the_rest(self):
        results = self.run_check(creds=None)
        self.assertEqual(results["login"].status, sc.FAIL)
        for key in ("scopes", "people", "chat", "sheets"):
            self.assertEqual(results[key].status, sc.SKIPPED)
        self.assertEqual(results["credentials"].status, sc.OK)

    def test_bad_credentials_file(self):
        self.credentials.write_text("{}", encoding="utf-8")
        self.assertEqual(self.run_check()["credentials"].status, sc.FAIL)

    def test_missing_scopes_fail_and_unknown_scopes_warn(self):
        self.creds.granted_scopes = SCOPES[:3]
        results = self.run_check()
        self.assertEqual(results["scopes"].status, sc.FAIL)
        self.assertIn("Google Chat memberships", results["scopes"].message)

        self.creds.granted_scopes = None
        with mock.patch("app.services.auth.urlopen", side_effect=OSError("offline")):
            self.assertEqual(self.run_check()["scopes"].status, sc.WARN)

    def test_network_error_is_reported_per_api(self):
        results = self.run_check(people=ConnectionError("offline"))
        self.assertEqual(results["people"].status, sc.FAIL)
        self.assertIn("internet", results["people"].message)


if __name__ == "__main__":
    unittest.main()
