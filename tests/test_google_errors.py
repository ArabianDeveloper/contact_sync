import unittest

from app.services.errors import (
    ALREADY_EXISTS, API_DISABLED, AUTH, BAD_REQUEST, INSUFFICIENT_SCOPE, NETWORK, NOT_FOUND, OTHER,
    PERMISSION, QUOTA, SERVER, describe_error,
)
from tests.fakes import FakeHttpError

DISABLED_BODY = {"error": {
    "code": 403,
    "message": "Google Chat API has not been used in project 123 before or it is disabled.",
    "status": "PERMISSION_DENIED",
    "details": [
        {"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": "SERVICE_DISABLED",
         "metadata": {"service": "chat.googleapis.com", "consumer": "projects/123"}},
        {"@type": "type.googleapis.com/google.rpc.Help",
         "links": [{"description": "activation", "url": "https://console.developers.google.com/apis/api/chat.googleapis.com/overview?project=123"}]},
    ],
}}


class DescribeErrorTests(unittest.TestCase):
    def kind(self, status, body=None):
        return describe_error(FakeHttpError(status, body)).kind

    def test_api_disabled(self):
        info = describe_error(FakeHttpError(403, DISABLED_BODY))
        self.assertEqual(info.kind, API_DISABLED)
        self.assertEqual(info.service, "Google Chat API")
        self.assertIn("Google Chat API is not enabled", info.message)
        self.assertTrue(info.help_url.startswith("https://console.developers.google.com"))
        self.assertTrue(info.is_fatal)

    def test_old_style_api_disabled(self):
        body = {"error": {"code": 403, "message": "x", "errors": [{"reason": "accessNotConfigured"}]}}
        self.assertEqual(self.kind(403, body), API_DISABLED)

    def test_insufficient_scope(self):
        body = {"error": {"code": 403, "message": "Request had insufficient authentication scopes.",
                          "details": [{"reason": "ACCESS_TOKEN_SCOPE_INSUFFICIENT"}]}}
        info = describe_error(FakeHttpError(403, body))
        self.assertEqual(info.kind, INSUFFICIENT_SCOPE)
        self.assertTrue(info.is_fatal)

    def test_status_codes(self):
        self.assertEqual(self.kind(401), AUTH)
        self.assertEqual(self.kind(429), QUOTA)
        self.assertEqual(self.kind(403), PERMISSION)
        self.assertEqual(self.kind(404), NOT_FOUND)
        self.assertEqual(self.kind(409), ALREADY_EXISTS)
        self.assertEqual(self.kind(400), BAD_REQUEST)
        self.assertEqual(self.kind(503), SERVER)
        self.assertEqual(self.kind(418), OTHER)

    def test_quota_by_reason_and_rpc_status(self):
        body = {"error": {"code": 403, "message": "Rate limit", "errors": [{"reason": "rateLimitExceeded"}]}}
        self.assertEqual(self.kind(403, body), QUOTA)
        self.assertEqual(self.kind(400, {"error": {"status": "RESOURCE_EXHAUSTED"}}), QUOTA)

    def test_permission_and_quota_are_not_fatal(self):
        self.assertFalse(describe_error(FakeHttpError(403)).is_fatal)
        self.assertFalse(describe_error(FakeHttpError(429)).is_fatal)
        self.assertFalse(describe_error(FakeHttpError(500)).is_fatal)
        self.assertTrue(describe_error(FakeHttpError(401)).is_fatal)

    def test_non_json_body_and_google_message_is_included(self):
        self.assertEqual(self.kind(500, b"<html>oops</html>"), SERVER)
        info = describe_error(FakeHttpError(404, {"error": {"message": "Space not found"}}))
        self.assertIn("Space not found", info.message)

    def test_non_http_errors(self):
        class RefreshError(Exception):
            pass

        class ServerNotFoundError(Exception):
            pass

        self.assertEqual(describe_error(RefreshError("invalid_grant")).kind, AUTH)
        self.assertEqual(describe_error(ConnectionError("x")).kind, NETWORK)
        self.assertEqual(describe_error(TimeoutError()).kind, NETWORK)
        self.assertEqual(describe_error(ServerNotFoundError("dns")).kind, NETWORK)
        self.assertEqual(describe_error(FileNotFoundError("x")).kind, OTHER)
        self.assertEqual(describe_error(ValueError("boom")).message, "boom")


if __name__ == "__main__":
    unittest.main()
