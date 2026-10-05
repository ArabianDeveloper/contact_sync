"""Realistic data: the whole pipeline (read, map, validate, merge duplicates) on files that contain
the usual problems. Uses the real phonenumbers / email-validator when they are installed."""
import importlib.util
import unittest
from pathlib import Path

from app.core.cleaning import NameOptions
from app.core.header_suggest import suggest_mapping
from app.core.pipeline import process_table
from app.core.readers import read_file
from tests.fakes import patch_fake_libraries, real_libraries_available

SAMPLES = Path(__file__).parent / "sample_files"

# row number (in the CSV) -> (name, phone, labels) of the rows that must be imported
VALID = {
    3: ("محمد سالم العلوي", "+96898123456", ["الفريق الأول"]),
    4: ("Sara Khan", "+96895123456", ["Team1"]),
    5: ("John Smith", "+96891234567", ["Team3", "Team4"]),
    6: ("Omar Said", "+96872123456", ["Team1", "Team2"]),
    7: ("Layla Hassan", "+96899123456", ["Team1", "Team2", "Team5"]),     # row 2 merged into it
    14: ("Hidden Chars", "+96899123470", ["Team1"]),
    15: ("Mixed عربي Name", "+96879123456", ["Team6"]),                    # mixed names are untouched
    16: ("خالد", "+96899323456", ["الفريق الثاني", "الفريق الأول"]),
    17: ("Arabic Comma Label", "+96899423456", ["الفريق،الثالث"]),         # the Arabic comma is not a separator
}
REJECTED = {
    8: ["Missing phone"],
    9: ["Invalid phone"],
    10: ["Missing email"],
    11: ["Invalid email"],
    12: ["Missing labels"],
    13: ["Missing name"],
    18: ["Missing name", "Missing phone", "Missing labels"],
}
DISTINCT_LABELS = ["الفريق الأول", "Team1", "Team3", "Team4", "Team2", "Team5", "Team6",
                   "الفريق الثاني", "الفريق،الثالث"]


class AcceptanceBase(unittest.TestCase):
    def setUp(self):
        if not real_libraries_available():
            self.addCleanup(patch_fake_libraries().stop)

    def check(self, result, offset=0):
        self.assertEqual(result.total_rows, 17)
        self.assertEqual((result.valid_count, result.rejected_count, result.duplicate_count), (9, 7, 1))

        valid = {r.row_number - offset: (r.name, r.phone, r.labels) for r in result.valid_rows}
        self.assertEqual(valid, VALID)
        rejected = {r.row_number - offset: r.reasons for r in result.rejected}
        self.assertEqual(rejected, REJECTED)

        duplicate = result.duplicates[0]
        self.assertEqual((duplicate.row_number - offset, duplicate.kept_row_number - offset), (2, 7))
        self.assertEqual(duplicate.name, "Ahmed Salim Al Balushi")
        self.assertEqual(result.distinct_labels(), DISTINCT_LABELS)
        self.assertEqual([r.email for r in result.valid_rows if r.row_number - offset == 7], ["layla@example.com"])


class CsvTests(AcceptanceBase):
    def run_file(self, name):
        table = read_file(SAMPLES / name)
        mapping = suggest_mapping(table.headers())
        self.assertTrue(mapping.is_complete())
        return process_table(table, mapping, NameOptions())

    def test_utf8_csv_with_bom(self):
        self.check(self.run_file("acceptance_contacts.csv"))

    def test_windows_1256_csv(self):
        self.check(self.run_file("acceptance_contacts_cp1256.csv"))


@unittest.skipUnless(importlib.util.find_spec("python_calamine"), "python-calamine is not installed")
class XlsxTests(AcceptanceBase):
    def test_xlsx_with_arabic_headers_title_row_and_numeric_phone(self):
        table = read_file(SAMPLES / "acceptance_arabic_headers.xlsx")
        self.assertEqual(table.sheet_name, "جهات الاتصال")
        self.assertEqual(table.header_row, 2)                       # the title row is skipped
        mapping = suggest_mapping(table.headers())
        self.assertEqual(mapping.name_columns, [0, 1, 2])
        self.assertTrue(mapping.is_complete())
        self.check(process_table(table, mapping, NameOptions()), offset=2)    # the rows are 2 lower in this file


class TemplateTests(AcceptanceBase):
    def test_real_import_template(self):
        table = read_file(SAMPLES / "real_test_template.csv")
        result = process_table(table, suggest_mapping(table.headers()), NameOptions())
        self.assertEqual((result.total_rows, result.valid_count, result.rejected_count, result.duplicate_count), (4, 3, 0, 1))
        merged = {r.phone: r.labels for r in result.valid_rows}
        self.assertEqual(merged["+96871000001"], ["ZZ-Test-A", "ZZ-Test-B", "ZZ-Test-C"])


if __name__ == "__main__":
    unittest.main()
