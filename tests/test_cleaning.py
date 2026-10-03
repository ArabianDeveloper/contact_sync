import unittest

from app.core.cleaning import (
    NameOptions, build_name, capitalize_words, clean_phone_text, contains_arabic,
    is_valid_email, normalize_digits, parse_phone, remove_hidden_characters, split_labels,
)
from tests.fakes import patch_fake_libraries, real_libraries_available


class CharacterTests(unittest.TestCase):
    def test_contains_arabic(self):
        self.assertTrue(contains_arabic("محمد"))
        self.assertTrue(contains_arabic("Ali محمد"))
        self.assertFalse(contains_arabic("Ahmed"))
        self.assertFalse(contains_arabic("12345"))
        self.assertFalse(contains_arabic(""))

    def test_normalize_digits(self):
        self.assertEqual(normalize_digits("٠١٢٣٤٥٦٧٨٩"), "0123456789")
        self.assertEqual(normalize_digits("۰۱۲۳۴۵۶۷۸۹"), "0123456789")
        self.assertEqual(normalize_digits("+968 ٩٩"), "+968 99")

    def test_remove_hidden_characters(self):
        self.assertEqual(remove_hidden_characters("\u200e+968\u200f 99\u200b123456\ufeff"), "+968 99123456")
        self.assertEqual(remove_hidden_characters("99\u00a0123"), "99 123")
        self.assertEqual(remove_hidden_characters("a\tb"), "a b")


class MissingLibraryTests(unittest.TestCase):
    def test_missing_libraries_give_a_readable_error(self):
        import sys
        from unittest import mock
        from app.core.errors import MissingLibraryError
        with mock.patch.dict(sys.modules, {"phonenumbers": None, "email_validator": None}):
            with self.assertRaises(MissingLibraryError):
                parse_phone("99123456")
            with self.assertRaises(MissingLibraryError):
                is_valid_email("a@b.com")


class PhoneTextTests(unittest.TestCase):
    def test_clean_phone_text(self):
        cases = {
            "+968 9912-3456": "+96899123456",
            "٩٩١٢٣٤٥٧": "99123457",
            "\u200e+968 99123456\u200f": "+96899123456",
            "0096899123456": "+96899123456",
            "(968) 99123456": "96899123456",
            "99.12.34.56": "99123456",
            "  99123456  ": "99123456",
            "": "",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(clean_phone_text(raw), expected)

    def test_letters_are_kept_so_the_number_is_rejected(self):
        self.assertEqual(clean_phone_text("99123456 ext 5"), "99123456ext5")
        self.assertIsNone(parse_phone("99123456 ext 5"))
        self.assertIsNone(parse_phone("abc"))
        self.assertIsNone(parse_phone(""))


class PhoneWithFakeLibraryTests(unittest.TestCase):
    """Tests the program's own code with a fake 'phonenumbers'."""

    def setUp(self):
        self.addCleanup(patch_fake_libraries().stop)

    def test_parse_phone(self):
        self.assertEqual(parse_phone("99123456"), "+96899123456")
        self.assertEqual(parse_phone("+968 9912 3456"), "+96899123456")
        self.assertEqual(parse_phone("٩٩١٢٣٤٥٧"), "+96899123457")
        self.assertEqual(parse_phone("00968 99123456"), "+96899123456")
        self.assertIsNone(parse_phone("12345"))


@unittest.skipUnless(real_libraries_available(), "real phonenumbers / email-validator not installed")
class RealLibraryTests(unittest.TestCase):
    """Run on a machine where the real libraries are installed."""

    def test_oman_numbers(self):
        self.assertEqual(parse_phone("99123456"), "+96899123456")
        self.assertEqual(parse_phone("+968 9912 3456"), "+96899123456")
        self.assertEqual(parse_phone("0096899123456"), "+96899123456")
        self.assertEqual(parse_phone("96899123456"), "+96899123456")
        self.assertEqual(parse_phone("٩٩١٢٣٤٥٧"), "+96899123457")
        self.assertEqual(parse_phone("\u200e+968 99123456\u200f"), "+96899123456")

    def test_other_country_and_invalid(self):
        self.assertEqual(parse_phone("+971501234567"), "+971501234567")
        self.assertIsNone(parse_phone("12345"))
        self.assertIsNone(parse_phone("00000000"))
        self.assertIsNone(parse_phone("+968 123"))

    def test_emails(self):
        for good in ("ahmed@example.com", " sara@example.com ", "a.b+c@sub.example.org"):
            with self.subTest(good=good):
                self.assertTrue(is_valid_email(good))
        for bad in ("", "john@example", "no-at-sign.com", "a@@b.com", "a b@example.com"):
            with self.subTest(bad=bad):
                self.assertFalse(is_valid_email(bad))


class EmailWithFakeLibraryTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(patch_fake_libraries().stop)

    def test_is_valid_email(self):
        self.assertTrue(is_valid_email(" ahmed@example.com "))
        self.assertFalse(is_valid_email(""))
        self.assertFalse(is_valid_email("   "))
        self.assertFalse(is_valid_email("john@example"))


class NameTests(unittest.TestCase):
    def test_english_default_options(self):
        self.assertEqual(build_name(["  ahmed ", "SALIM", "al   balushi"]), "Ahmed Salim Al Balushi")

    def test_empty_parts_are_skipped_and_all_empty_gives_empty(self):
        self.assertEqual(build_name(["John", "", "doe"]), "John Doe")
        self.assertEqual(build_name(["", "  ", ""]), "")
        self.assertEqual(build_name([]), "")

    def test_arabic_name_is_untouched(self):
        self.assertEqual(build_name(["محمد ", " سالم", "العلوي"]), "محمد   سالم العلوي")
        self.assertEqual(build_name(["ali ", "محمد"]), "ali  محمد")   # mixed names are untouched

    def test_options_can_be_turned_off(self):
        off = NameOptions(trim=False, collapse_spaces=False, capitalize=False)
        self.assertEqual(build_name(["  john ", "DOE"], off), "  john  DOE")
        only_capitalize = NameOptions(trim=False, collapse_spaces=False, capitalize=True)
        self.assertEqual(build_name(["john"], only_capitalize), "John")
        only_collapse = NameOptions(trim=False, collapse_spaces=True, capitalize=False)
        self.assertEqual(build_name(["a  b"], only_collapse), "a b")

    def test_capitalize_rules(self):
        cases = {
            "john smith": "John Smith",
            "JOHN SMITH": "John Smith",
            "AL-BALUSHI": "Al-Balushi",
            "o'neil": "O'Neil",
            "mary-ann": "Mary-Ann",
            "McDonald": "McDonald",          # mixed case is kept
            "iPhone": "iPhone",
            "a": "A",
            "123": "123",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(capitalize_words(raw), expected)


class LabelTests(unittest.TestCase):
    def test_split_labels(self):
        self.assertEqual(split_labels("Team1, Team2 ,Team3"), ["Team1", "Team2", "Team3"])
        self.assertEqual(split_labels("Team1,,Team2,"), ["Team1", "Team2"])
        self.assertEqual(split_labels(" , ,"), [])
        self.assertEqual(split_labels(""), [])
        self.assertEqual(split_labels("Team1,team1, TEAM1"), ["Team1"])
        self.assertEqual(split_labels("الفريق الأول,الفريق الثاني"), ["الفريق الأول", "الفريق الثاني"])

    def test_only_comma_separates(self):
        self.assertEqual(split_labels("Team1;Team2"), ["Team1;Team2"])
        self.assertEqual(split_labels("الفريق،الثاني"), ["الفريق،الثاني"])   # Arabic comma is not a separator (D5)


if __name__ == "__main__":
    unittest.main()
