import unittest
from pathlib import Path

from app.core.cleaning import NameOptions
from app.core.models import Mapping, SourceTable
from app.core.pipeline import process_table
from app.core.readers import read_file
from app.core.validation import validate_rows
from tests.fakes import patch_fake_libraries

SAMPLES = Path(__file__).parent / "sample_files"
MAPPING = Mapping(name_columns=[0, 1, 2], phone_column=3, email_column=4, labels_column=5)


def make_table(*rows):
    return SourceTable(
        rows=[["First", "Middle", "Family", "Phone", "Email", "Labels"], *rows],
        file_type="csv",
    )


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(patch_fake_libraries().stop)

    def test_sample_file(self):
        table = read_file(SAMPLES / "contacts_utf8.csv")
        result = process_table(table, MAPPING)
        self.assertEqual(result.total_rows, 4)
        self.assertEqual(result.valid_count, 3)
        self.assertEqual(result.rejected_count, 1)

        by_row = {r.row_number: r for r in result.valid_rows}
        self.assertEqual(by_row[2].name, "Ahmed Salim Al Balushi")
        self.assertEqual(by_row[2].phone, "+96899123456")
        self.assertEqual(by_row[2].labels, ["Team1", "Team2"])
        self.assertEqual(by_row[3].name, "محمد سالم العلوي")          # Arabic untouched
        self.assertEqual(by_row[3].phone, "+96899123457")             # Arabic digits converted
        self.assertEqual(by_row[3].labels, ["الفريق الأول"])
        self.assertEqual(by_row[4].phone, "+96899123458")

        rejected = result.rejected[0]
        self.assertEqual(rejected.row_number, 5)
        self.assertEqual(rejected.reasons, ["Missing phone", "Invalid email"])
        self.assertEqual(rejected.name, "John Doe")

    def test_row_numbers_follow_the_original_file(self):
        table = read_file(SAMPLES / "contacts_title_row.csv")   # header on row 3
        result = process_table(table, MAPPING)
        self.assertEqual([r.row_number for r in result.valid_rows], [4, 5, 6])
        self.assertEqual(result.rejected[0].row_number, 7)

    def test_all_reasons(self):
        table = make_table(
            ["", "", "", "", "", ""],                          # empty row: skipped, not counted
            ["", " ", "", "abc", "bad", " , "],                # every field wrong
            ["Ali", "", "X", "99123456", "", "T1"],            # missing email
        )
        result = validate_rows(table, MAPPING)
        self.assertEqual(result.total_rows, 2)
        self.assertEqual(
            result.rejected[0].reasons,
            ["Missing name", "Invalid phone", "Invalid email", "Missing labels"],
        )
        self.assertEqual(result.rejected[1].reasons, ["Missing email"])

    def test_duplicates_are_removed_among_valid_rows_only(self):
        table = make_table(
            ["Ali", "", "A", "99123456", "bad", "T0"],                 # invalid email, same phone
            ["Ali", "", "A", "99123456", "ali@x.com", "Team1"],
            ["Ali", "", "B", "+968 9912 3456", "ali2@x.com", "Team2"],
            ["Sara", "", "K", "99123457", "s@x.com", "Team1"],
        )
        result = process_table(table, MAPPING)
        self.assertEqual(result.total_rows, 4)
        self.assertEqual(result.rejected_count, 1)                    # row 2 is reported as rejected only
        self.assertEqual(result.duplicate_count, 1)
        self.assertEqual(result.duplicates[0].row_number, 3)
        self.assertEqual(result.duplicates[0].kept_row_number, 4)
        kept = {r.row_number: r for r in result.valid_rows}
        self.assertEqual(kept[4].labels, ["Team1", "Team2"])          # T0 of the rejected row is not merged
        self.assertEqual(kept[4].email, "ali2@x.com")                 # the last row is kept
        self.assertEqual(result.distinct_labels(), ["Team1", "Team2"])

    def test_incomplete_mapping_raises(self):
        with self.assertRaises(ValueError):
            validate_rows(make_table(), Mapping(name_columns=[0], phone_column=3))

    def test_name_options_are_used(self):
        table = make_table(["ali", "", "khan", "99123456", "a@x.com", "T"])
        off = NameOptions(trim=True, collapse_spaces=True, capitalize=False)
        self.assertEqual(validate_rows(table, MAPPING, off).valid_rows[0].name, "ali khan")


if __name__ == "__main__":
    unittest.main()
