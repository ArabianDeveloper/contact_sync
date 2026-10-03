import sys
import types
import unittest
from pathlib import Path
from unittest import mock

from app.core.errors import ReadError, UnsupportedFileError
from app.core.models import SourceTable, column_letter
from app.core.readers import detect_file_type, read_file
from app.core.readers.cells import cell_to_text
from app.core.readers.csv_reader import detect_delimiter
from app.core.readers.excel_reader import read_excel
from app.core.readers.header import guess_header_row
from app.core.readers.text_encoding import detect_encoding

SAMPLES = Path(__file__).parent / "sample_files"
HEADERS = ["First Name", "Middle Name", "Family Name", "Phone", "Email", "Labels"]


class DetectTypeTests(unittest.TestCase):
    def test_every_sample_type(self):
        expected = {
            "contacts.xlsx": "xlsx",
            "contacts.xls": "xls",
            "contacts.ods": "ods",
            "contacts_utf8.csv": "csv",
            "contacts_utf8_bom.csv": "csv",
            "contacts_cp1256.csv": "csv",
            "contacts_semicolon.csv": "csv",
            "contacts.tsv": "tsv",
            "contacts_objects.json": "json",
            "contacts_lists.json": "json",
        }
        for name, file_type in expected.items():
            with self.subTest(name=name):
                self.assertEqual(detect_file_type(SAMPLES / name), file_type)

    def test_content_wins_over_extension(self):
        import shutil, tempfile
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "data.xlsx"          # extension says XLSX, content is CSV
            shutil.copy(SAMPLES / "contacts_utf8.csv", fake)
            self.assertEqual(detect_file_type(fake), "csv")
            real = Path(tmp) / "data.csv"           # extension says CSV, content is XLSX
            shutil.copy(SAMPLES / "contacts.xlsx", real)
            self.assertEqual(detect_file_type(real), "xlsx")

    def test_errors(self):
        with self.assertRaises(ReadError):
            detect_file_type(SAMPLES / "empty.csv")
        with self.assertRaises(UnsupportedFileError):
            detect_file_type(SAMPLES / "not_spreadsheet.zip")
        with self.assertRaises(UnsupportedFileError):
            detect_file_type(SAMPLES / "binary.bin")
        with self.assertRaises(UnsupportedFileError):
            detect_file_type(SAMPLES / "does_not_exist.csv")


class EncodingTests(unittest.TestCase):
    def test_utf8_bom_and_plain(self):
        self.assertEqual(detect_encoding((SAMPLES / "contacts_utf8.csv").read_bytes()), "utf-8")
        self.assertEqual(detect_encoding((SAMPLES / "contacts_utf8_bom.csv").read_bytes()), "utf-8-sig")

    def test_windows_1256_is_read_as_arabic(self):
        table = read_file(SAMPLES / "contacts_cp1256.csv")
        names = [row[0] for _, row in table.data_rows()]
        self.assertIn("محمد", names)


class CsvTests(unittest.TestCase):
    def test_utf8_csv_with_arabic(self):
        table = read_file(SAMPLES / "contacts_utf8.csv")
        self.assertEqual(table.file_type, "csv")
        self.assertEqual(table.delimiter, ",")
        self.assertEqual(table.headers(), HEADERS)
        data = dict(table.data_rows())
        self.assertEqual(data[3][0], "محمد")
        self.assertEqual(data[3][3], "٩٩١٢٣٤٥٧")          # digits are kept as read
        self.assertEqual(data[2][5], "Team1,Team2")      # quoted field with a comma stays whole

    def test_bom_is_removed(self):
        table = read_file(SAMPLES / "contacts_utf8_bom.csv")
        self.assertEqual(table.headers()[0], "First Name")

    def test_semicolon_and_tab(self):
        self.assertEqual(read_file(SAMPLES / "contacts_semicolon.csv").delimiter, ";")
        tsv = read_file(SAMPLES / "contacts.tsv")
        self.assertEqual(tsv.file_type, "tsv")
        self.assertEqual(tsv.delimiter, "\t")
        self.assertEqual(tsv.headers(), HEADERS)

    def test_title_row_is_skipped_by_header_guess(self):
        table = read_file(SAMPLES / "contacts_title_row.csv")
        self.assertEqual(table.header_row, 2)
        self.assertEqual(table.headers(), HEADERS)
        first_number, _ = next(table.data_rows())
        self.assertEqual(first_number, 4)                # row number in the original file

    def test_delimiter_detection_edge_cases(self):
        self.assertEqual(detect_delimiter("a;b;c\n1;2;3\n"), ";")
        self.assertEqual(detect_delimiter("only one column\nsecond\n"), ",")
        self.assertEqual(detect_delimiter(""), ",")


class JsonTests(unittest.TestCase):
    def test_list_of_objects(self):
        table = read_file(SAMPLES / "contacts_objects.json")
        self.assertEqual(table.headers(), HEADERS)
        self.assertEqual(len(list(table.data_rows())), 4)

    def test_list_of_lists(self):
        table = read_file(SAMPLES / "contacts_lists.json")
        self.assertEqual(table.headers(), HEADERS)

    def test_unsupported_shape(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.json"
            path.write_text('{"a": 1}', encoding="utf-8")
            # a JSON object is valid JSON, so detection says json and reading explains the shape
            with self.assertRaises(ReadError):
                read_file(path)


class ModelTests(unittest.TestCase):
    def test_column_letter(self):
        self.assertEqual([column_letter(i) for i in (0, 1, 25, 26, 27, 51, 52)],
                         ["A", "B", "Z", "AA", "AB", "AZ", "BA"])

    def test_empty_headers_get_names_and_empty_rows_are_skipped(self):
        table = SourceTable(
            rows=[["Name", "", "Phone"], ["a", "b"], ["", "", ""], ["c", "d", "e"]],
            file_type="csv",
        )
        self.assertEqual(table.headers(), ["Name", "Column B", "Phone"])
        self.assertEqual(list(table.data_rows()), [(2, ["a", "b", ""]), (4, ["c", "d", "e"])])

    def test_set_header_row_validates(self):
        table = SourceTable(rows=[["a"], ["b"]], file_type="csv")
        table.set_header_row(1)
        self.assertEqual(table.headers(), ["b"])
        with self.assertRaises(ValueError):
            table.set_header_row(5)

    def test_preview_limit(self):
        table = SourceTable(rows=[["h"]] + [[str(i)] for i in range(500)], file_type="csv")
        self.assertEqual(len(table.preview()), 100)
        self.assertEqual(len(table.preview(5)), 5)


class CellAndHeaderTests(unittest.TestCase):
    def test_cell_to_text(self):
        self.assertEqual(cell_to_text(99123456.0), "99123456")
        self.assertEqual(cell_to_text(99123456), "99123456")
        self.assertEqual(cell_to_text(1.5), "1.5")
        self.assertEqual(cell_to_text(None), "")
        self.assertEqual(cell_to_text(True), "TRUE")
        self.assertEqual(cell_to_text(float("nan")), "")
        self.assertEqual(cell_to_text("محمد"), "محمد")

    def test_guess_header_row(self):
        rows = [["Title"], [], ["Name", "Phone", "Email"], ["Ali", "99123456", "a@b.com"]]
        self.assertEqual(guess_header_row(rows), 2)
        self.assertEqual(guess_header_row([]), 0)
        self.assertEqual(guess_header_row([["1", "2"], ["3", "4"]]), 0)


def _fake_calamine(sheets):
    class FakeSheet:
        def __init__(self, rows):
            self.rows = rows
            self.kwargs = None

        def to_python(self, **kwargs):
            FakeSheet.last_kwargs = kwargs
            return self.rows

    class FakeWorkbook:
        sheet_names = list(sheets)

        @classmethod
        def from_path(cls, path):
            return cls()

        def get_sheet_by_name(self, name):
            return FakeSheet(sheets[name])

    module = types.ModuleType("python_calamine")
    module.CalamineWorkbook = FakeWorkbook
    module.FakeSheet = FakeSheet
    return module


class ExcelReaderWithFakeLibraryTests(unittest.TestCase):
    """The real library is not installed in the test environment, so a fake one is used.
    Reading real XLSX, XLS and ODS files must be checked with inspect_file.py."""

    def setUp(self):
        self.fake = _fake_calamine({
            "Sheet1": [["Name", "Phone"], ["Ali", 99123456.0], [None, None], [None, None]],
            "Other": [["Name"], ["Sara"]],
        })
        patcher = mock.patch.dict(sys.modules, {"python_calamine": self.fake})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_first_sheet_is_default_and_numbers_become_text(self):
        table = read_excel(Path("x.xlsx"), "xlsx")
        self.assertEqual(table.sheet_names, ["Sheet1", "Other"])
        self.assertEqual(table.sheet_name, "Sheet1")
        self.assertEqual(table.rows, [["Name", "Phone"], ["Ali", "99123456"]])
        self.assertEqual(self.fake.FakeSheet.last_kwargs, {"skip_empty_area": False})

    def test_sheet_selection_and_errors(self):
        self.assertEqual(read_excel(Path("x.xlsx"), "xlsx", "Other").rows, [["Name"], ["Sara"]])
        with self.assertRaises(ReadError):
            read_excel(Path("x.xlsx"), "xlsx", "Missing")


if __name__ == "__main__":
    unittest.main()
