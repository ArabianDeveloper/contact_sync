import json
import logging
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app import paths
from app.logging_setup import setup_logging, shutdown_logging
from app.settings import Settings, load_settings, save_settings


class AppDataTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        patcher = mock.patch.dict(os.environ, {"APPDATA": self.tmp.name})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(shutdown_logging)


class PathsTests(AppDataTestCase):
    def test_folders_are_created_under_appdata(self):
        self.assertEqual(paths.app_data_dir(), Path(self.tmp.name) / "ContactSync")
        self.assertTrue(paths.logs_dir().is_dir())
        self.assertEqual(paths.token_path().name, "token.json")
        self.assertEqual(paths.settings_path().name, "settings.json")
        self.assertEqual(paths.profiles_path().name, "mapping_profiles.json")


class SettingsTests(AppDataTestCase):
    def test_defaults_when_file_is_missing(self):
        s = load_settings()
        self.assertTrue(s.auto_create_labels)
        self.assertTrue(s.auto_create_spaces)
        self.assertTrue(s.name_trim and s.name_collapse_spaces and s.name_capitalize)
        self.assertIsNone(s.credentials_path)

    def test_round_trip_with_arabic_path(self):
        s = Settings(credentials_path="C:\\مجلد\\credentials.json", auto_create_spaces=False)
        save_settings(s)
        loaded = load_settings()
        self.assertEqual(loaded, s)

    def test_corrupt_file_gives_defaults(self):
        paths.settings_path().write_text("{not json", encoding="utf-8")
        self.assertEqual(load_settings(), Settings())

    def test_wrong_types_are_ignored(self):
        paths.settings_path().write_text(
            json.dumps({"auto_create_labels": "no", "credentials_path": 5, "name_trim": False}),
            encoding="utf-8",
        )
        s = load_settings()
        self.assertTrue(s.auto_create_labels)
        self.assertIsNone(s.credentials_path)
        self.assertFalse(s.name_trim)


class LoggingTests(AppDataTestCase):
    def test_log_file_is_written_and_setup_is_idempotent(self):
        logger = setup_logging()
        setup_logging()
        self.assertEqual(
            len([h for h in logger.handlers if h.get_name() == "contact_sync_file"]), 1
        )
        logging.getLogger("contact_sync.test").info("hello")
        for h in logger.handlers:
            h.flush()
        self.assertIn("hello", paths.log_file_path().read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
