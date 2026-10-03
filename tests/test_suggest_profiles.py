import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.core.header_suggest import classify_header, normalize_header, suggest_mapping
from app.core.models import Mapping
from app.core.profiles import (
    find_profile, mapping_to_profile, profile_key, profile_to_mapping, save_profile,
)


class SuggestTests(unittest.TestCase):
    def test_english_headers(self):
        m = suggest_mapping(["First Name", "Middle Name", "Family Name", "Phone", "Email", "Labels"])
        self.assertEqual(m.name_columns, [0, 1, 2])
        self.assertEqual((m.phone_column, m.email_column, m.labels_column), (3, 4, 5))
        self.assertTrue(m.is_complete())

    def test_arabic_headers(self):
        m = suggest_mapping(["الاسم الأول", "اسم العائلة", "رقم الهاتف", "البريد الإلكتروني", "الفريق"])
        self.assertEqual(m.name_columns, [0, 1])
        self.assertEqual((m.phone_column, m.email_column, m.labels_column), (2, 3, 4))

    def test_other_spellings(self):
        self.assertEqual(classify_header("E-mail"), "email")
        self.assertEqual(classify_header("MOBILE"), "phone")
        self.assertEqual(classify_header("الجوال"), "phone")
        self.assertEqual(classify_header("المجموعة"), "labels")
        self.assertEqual(classify_header("Full Name"), "name")
        self.assertEqual(classify_header("Notes"), None)
        self.assertEqual(classify_header("Column A"), None)

    def test_short_name_headers(self):
        m = suggest_mapping(["First", "Middle", "Last", "Family", "Phone", "Email", "Labels"])
        self.assertEqual(m.name_columns, [0, 1, 2, 3])
        self.assertTrue(m.is_complete())

    def test_team_name_is_labels_not_name(self):
        m = suggest_mapping(["Name", "Team Name", "Mobile", "Mail"])
        self.assertEqual(m.name_columns, [0])
        self.assertEqual(m.labels_column, 1)

    def test_first_match_wins_and_nothing_found(self):
        m = suggest_mapping(["Phone", "Mobile"])
        self.assertEqual(m.phone_column, 0)
        self.assertFalse(m.is_complete())
        self.assertEqual(suggest_mapping(["A", "B"]), Mapping())

    def test_normalize_header(self):
        self.assertEqual(normalize_header("  E-Mail  Address "), "e mail address")
        self.assertEqual(normalize_header("الإلكتروني"), normalize_header("الالكتروني"))


class ProfileTests(unittest.TestCase):
    HEADERS = ["First", "Family", "Mobile", "Mail", "Group"]
    MAPPING = Mapping(name_columns=[0, 1], phone_column=2, email_column=3, labels_column=4)

    def test_round_trip_and_reordered_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profiles.json"
            self.assertIsNone(find_profile(self.HEADERS, path))
            save_profile(self.HEADERS, self.MAPPING, path)
            self.assertEqual(find_profile(self.HEADERS, path), self.MAPPING)

            reordered = ["Group", "Mail", "Mobile", "Family", "First"]
            found = find_profile(reordered, path)
            self.assertEqual(found, Mapping(name_columns=[4, 3], phone_column=2, email_column=1, labels_column=0))

            self.assertEqual(find_profile([" first ", "FAMILY", "mobile", "mail", "group"], path), self.MAPPING)
            self.assertIsNone(find_profile(["First", "Family", "Mobile", "Mail"], path))   # other layout

    def test_arabic_headers_are_saved(self):
        headers = ["الاسم", "الهاتف", "البريد", "الفريق"]
        mapping = Mapping(name_columns=[0], phone_column=1, email_column=2, labels_column=3)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profiles.json"
            save_profile(headers, mapping, path)
            self.assertEqual(find_profile(headers, path), mapping)

    def test_duplicate_header_names_do_not_apply(self):
        profile = mapping_to_profile(self.MAPPING, self.HEADERS)
        self.assertIsNone(profile_to_mapping(profile, self.HEADERS + ["Mobile"]))

    def test_corrupt_file_and_default_location(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profiles.json"
            path.write_text("{broken", encoding="utf-8")
            self.assertIsNone(find_profile(self.HEADERS, path))
            save_profile(self.HEADERS, self.MAPPING, path)       # a corrupt file is replaced
            self.assertEqual(find_profile(self.HEADERS, path), self.MAPPING)
            with mock.patch.dict(os.environ, {"APPDATA": tmp}):
                save_profile(self.HEADERS, self.MAPPING)
                self.assertEqual(find_profile(self.HEADERS), self.MAPPING)
                self.assertTrue((Path(tmp) / "ContactSync" / "mapping_profiles.json").exists())

    def test_key_ignores_order_and_case(self):
        self.assertEqual(profile_key(["A", "b"]), profile_key([" B", "a "]))
        self.assertNotEqual(profile_key(["A", "b"]), profile_key(["A", "c"]))


if __name__ == "__main__":
    unittest.main()
