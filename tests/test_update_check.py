import io
import json
import unittest
from urllib.error import HTTPError, URLError

from app.config import GITHUB_REPO
from app.update_check import check_for_update, parse_version


def opener_returning(data):
    seen = {}

    def opener(request, timeout=None):
        seen["url"], seen["timeout"], seen["headers"] = request.full_url, timeout, dict(request.header_items())
        body = data if isinstance(data, bytes) else json.dumps(data).encode("utf-8")
        return io.BytesIO(body)

    opener.seen = seen
    return opener


class UpdateCheckTests(unittest.TestCase):
    def test_the_configured_repository(self):
        self.assertEqual(GITHUB_REPO, "ArabianDeveloper/contact_sync")

    def test_newer_release(self):
        opener = opener_returning({"tag_name": "v1.2.0", "html_url": "https://github.com/ArabianDeveloper/contact_sync/releases/tag/v1.2.0"})
        info = check_for_update("ArabianDeveloper/contact_sync", "1.0.0", opener=opener)
        self.assertEqual((info.version, info.url),
                         ("1.2.0", "https://github.com/ArabianDeveloper/contact_sync/releases/tag/v1.2.0"))
        self.assertEqual(opener.seen["url"], "https://api.github.com/repos/ArabianDeveloper/contact_sync/releases/latest")
        self.assertEqual(opener.seen["timeout"], 5.0)
        self.assertIn("User-agent", opener.seen["headers"])

    def test_same_or_older_release(self):
        for tag in ("v1.0.0", "1.0.0", "v0.9.9"):
            with self.subTest(tag=tag):
                self.assertIsNone(check_for_update("a/b", "1.0.0", opener=opener_returning({"tag_name": tag})))

    def test_version_comparison_is_numeric(self):
        self.assertIsNotNone(check_for_update("a/b", "1.9.0", opener=opener_returning({"tag_name": "v1.10.0"})))

    def test_link_outside_github_is_not_used(self):
        info = check_for_update("a/b", "1.0.0", opener=opener_returning({"tag_name": "v2.0.0", "html_url": "https://evil.example/x"}))
        self.assertEqual(info.url, "https://github.com/a/b/releases/latest")
        info = check_for_update("a/b", "1.0.0", opener=opener_returning({"tag_name": "v2.0.0"}))
        self.assertEqual(info.url, "https://github.com/a/b/releases/latest")

    def test_every_failure_gives_none(self):
        def raising(error):
            def opener(request, timeout=None):
                raise error
            return opener

        for opener in (
            raising(HTTPError("u", 404, "Not Found", {}, None)),      # no release published yet
            raising(HTTPError("u", 403, "rate limit", {}, None)),
            raising(URLError("offline")),
            raising(TimeoutError()),
            opener_returning(b"<html>not json</html>"),
            opener_returning([1, 2]),
            opener_returning({"tag_name": "not a version"}),
            opener_returning({}),
        ):
            self.assertIsNone(check_for_update("a/b", "1.0.0", opener=opener))

    def test_invalid_repository_or_current_version(self):
        opener = opener_returning({"tag_name": "v2.0.0"})
        for repo in (None, "", "no-slash", "a/b/c", "a b/c"):
            self.assertIsNone(check_for_update(repo, "1.0.0", opener=opener))
        self.assertIsNone(check_for_update("a/b", "dev", opener=opener))

    def test_parse_version(self):
        self.assertEqual(str(parse_version("v1.2.3")), "1.2.3")
        self.assertIsNone(parse_version(""))
        self.assertIsNone(parse_version("latest"))


if __name__ == "__main__":
    unittest.main()
