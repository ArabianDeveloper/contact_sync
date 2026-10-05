import re
import sys
import unittest
from pathlib import Path
from unittest import mock

import build_exe
from app.config import VERSION
from app.crash import format_crash
from app.resources import resource_path

ROOT = Path(__file__).resolve().parent.parent


class VersionTests(unittest.TestCase):
    def test_version_tuple(self):
        self.assertEqual(build_exe.version_tuple("1.2.3"), (1, 2, 3, 0))
        self.assertEqual(build_exe.version_tuple("2.0"), (2, 0, 0, 0))
        self.assertEqual(build_exe.version_tuple("1.2.3.4"), (1, 2, 3, 4))
        self.assertEqual(build_exe.version_tuple("1.0.0-beta"), (1, 0, 0, 0))
        self.assertEqual(build_exe.version_tuple("x"), (0, 0, 0, 0))

    def test_version_info_text(self):
        text = build_exe.version_info_text("1.4.2")
        self.assertIn("filevers=(1, 4, 2, 0)", text)
        self.assertIn("StringStruct('FileVersion', '1.4.2.0')", text)
        self.assertIn("StringStruct('OriginalFilename', 'ContactSync.exe')", text)
        self.assertEqual(text.count("("), text.count(")"))      # balanced brackets

    def test_the_installer_and_the_program_use_the_same_version_source(self):
        self.assertTrue(re.fullmatch(r"\d+\.\d+\.\d+", VERSION), VERSION)


class IsccTests(unittest.TestCase):
    def test_search_order(self):
        none = lambda name: None
        self.assertEqual(build_exe.find_iscc({"ISCC": "C:\\x\\ISCC.exe"}, lambda p: True, none), "C:\\x\\ISCC.exe")
        self.assertEqual(build_exe.find_iscc({}, lambda p: False, lambda n: "C:\\path\\ISCC.exe"), "C:\\path\\ISCC.exe")
        env = {"ProgramFiles(x86)": "C:\\PF86"}
        expected = "C:\\PF86\\Inno Setup 6\\ISCC.exe"
        import os
        found = build_exe.find_iscc(env, lambda p: p == os.path.join("C:\\PF86", "Inno Setup 6", "ISCC.exe"), none)
        self.assertEqual(found, os.path.join("C:\\PF86", "Inno Setup 6", "ISCC.exe"))
        self.assertIsNone(build_exe.find_iscc({}, lambda p: False, none))

    def test_not_windows_is_refused(self):
        with mock.patch.object(sys, "platform", "linux"), mock.patch.object(sys, "argv", ["build_exe.py"]):
            self.assertEqual(build_exe.main(), 1)


class FilesTests(unittest.TestCase):
    def test_icon_is_a_valid_ico(self):
        data = (ROOT / "assets" / "icon.ico").read_bytes()
        self.assertEqual(data[:4], b"\x00\x00\x01\x00")          # ICO header
        self.assertGreater(data[4], 1)                           # several sizes

    def test_spec_is_valid_python_and_has_the_important_settings(self):
        source = (ROOT / "contact_sync.spec").read_text(encoding="utf-8")
        compile(source, "contact_sync.spec", "exec")
        for needle in ('"main.py"', 'name="ContactSync"', "console=False", "exclude_binaries=True",
                       'collect_data_files("googleapiclient")', "COLLECT("):
            self.assertIn(needle, source)

    def test_installer_script(self):
        script = (ROOT / "installer" / "contact_sync.iss").read_text(encoding="utf-8")
        self.assertIn("AppId={{AD98CD95-D778-48F0-94AB-94BDDCA83D45}", script)     # must never change
        self.assertIn("OutputBaseFilename=ContactSync-Setup-{#AppVersion}", script)
        self.assertIn(r'Source: "..\dist\ContactSync\*"', script)
        self.assertIn("DefaultDirName={autopf}", script)
        self.assertNotIn("UninstallDelete", script.replace("; The data", ""))      # user data is kept

    def test_requirements(self):
        build = (ROOT / "requirements-build.txt").read_text(encoding="utf-8")
        self.assertIn("pyinstaller", build)
        main = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        for library in ("PySide6", "packaging", "requests", "python-calamine", "phonenumbers", "email-validator",
                        "google-api-python-client", "google-auth-oauthlib", "charset-normalizer"):
            self.assertIn(library, main)


class RuntimeHelpersTests(unittest.TestCase):
    def test_resource_path(self):
        self.assertTrue(resource_path("assets/icon.ico").is_file())
        with mock.patch.object(sys, "_MEIPASS", "C:\\bundle", create=True):
            self.assertEqual(str(resource_path("assets/icon.ico")).replace("/", "\\"), "C:\\bundle\\assets\\icon.ico")

    def test_crash_text_has_no_error_message(self):
        secret = "secret" + "@example.com +96899123456"      # not written in the raising line
        try:
            raise ValueError(secret)
        except ValueError:
            exc_type, _, tb = sys.exc_info()
        text = format_crash(exc_type, tb)
        self.assertTrue(text.startswith("ValueError"))
        self.assertIn("test_packaging.py", text)
        self.assertNotIn("secret@example.com", text)
        self.assertNotIn("96899123456", text)


if __name__ == "__main__":
    unittest.main()
