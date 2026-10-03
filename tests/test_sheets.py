import unittest

from app.core.errors import ContactSyncError, ReadError
from app.core.readers.sheet_reader import range_offsets, read_sheet
from app.services.sheets import parse_sheet_id, quote_tab
from tests.fake_services import FakeSheets
from tests.fakes import FakeHttpError

ID = "1gXMz0Kj_t1FaoMyt2ygGjl9VTVfHuOHDzycycECefhQ"
HEADER = ["First", "Family", "Phone", "Email", "Labels"]


class ParseTests(unittest.TestCase):
    def test_parse_sheet_id(self):
        self.assertEqual(parse_sheet_id(ID), ID)
        self.assertEqual(parse_sheet_id(f"  https://docs.google.com/spreadsheets/d/{ID}/edit#gid=0 "), ID)
        self.assertEqual(parse_sheet_id(f"https://docs.google.com/spreadsheets/d/{ID}"), ID)
        for bad in ("", "   ", "short", "https://example.com/file", "not an id with spaces"):
            self.assertIsNone(parse_sheet_id(bad))

    def test_quote_tab(self):
        self.assertEqual(quote_tab("Team B"), "'Team B'")
        self.assertEqual(quote_tab("Ali's"), "'Ali''s'")
        self.assertEqual(quote_tab("الفريق"), "'الفريق'")

    def test_range_offsets(self):
        self.assertEqual(range_offsets(None), (0, 0))
        self.assertEqual(range_offsets(""), (0, 0))
        self.assertEqual(range_offsets("A1:F200"), (0, 0))
        self.assertEqual(range_offsets("C5:F9"), (4, 2))
        self.assertEqual(range_offsets("b:d"), (0, 1))
        self.assertEqual(range_offsets("AA3"), (2, 26))
        self.assertEqual(range_offsets("5:9"), (4, 0))


class ReadSheetTests(unittest.TestCase):
    def setUp(self):
        self.service = FakeSheets({
            "Sheet1": [HEADER, ["Ali", "Khan", "99123456", "a@x.com", "Team1"], ["محمد", "العلوي", "99123457", "m@x.com", "الفريق"], [], []],
            "Team B": [["Omar"]],
            "Ali's": [["x"]],
        })

    def test_first_tab_by_default_and_trailing_rows_removed(self):
        table = read_sheet(self.service, f"https://docs.google.com/spreadsheets/d/{ID}/edit")
        self.assertEqual(table.file_type, "gsheet")
        self.assertEqual(table.sheet_names, ["Sheet1", "Team B", "Ali's"])
        self.assertEqual(table.sheet_name, "Sheet1")
        self.assertEqual(len(table.rows), 3)
        self.assertEqual(table.headers(), HEADER)
        self.assertEqual(table.header_row, 0)
        self.assertEqual(self.service.calls[-1], ("values.get", ID, "'Sheet1'", "FORMATTED_VALUE"))

    def test_other_tab_and_quote(self):
        read_sheet(self.service, ID, sheet="Ali's")
        self.assertEqual(self.service.calls[-1][2], "'Ali''s'")

    def test_range_keeps_the_row_and_column_numbers_of_the_sheet(self):
        self.service.tabs["Sheet1"] = [["Name", "Phone"], ["Ali", "99123456"]]
        table = read_sheet(self.service, ID, cell_range="B3:C4")
        self.assertEqual(self.service.calls[-1][2], "'Sheet1'!B3:C4")
        self.assertEqual(table.rows[:2], [[], []])
        self.assertEqual(table.rows[2], ["", "Name", "Phone"])
        number, row = next(table.data_rows())          # the data row, with the real row number
        self.assertEqual(number, 4)

    def test_problems(self):
        with self.assertRaises(ReadError):
            read_sheet(self.service, "nonsense")
        with self.assertRaises(ReadError):
            read_sheet(self.service, ID, sheet="Missing")
        with self.assertRaises(ReadError):
            read_sheet(self.service, ID, cell_range="Sheet1!A1:B2")
        self.service.tabs["Empty"] = [[], []]
        with self.assertRaises(ReadError):
            read_sheet(self.service, ID, sheet="Empty")

    def test_google_errors_are_readable(self):
        self.service.errors["get"] = FakeHttpError(404, {"error": {"message": "Requested entity was not found."}})
        with self.assertRaises(ContactSyncError) as ctx:
            read_sheet(self.service, ID)
        self.assertIn("not found", str(ctx.exception))

        self.service.errors["get"] = FakeHttpError(403, {"error": {"status": "PERMISSION_DENIED"}})
        with self.assertRaises(ContactSyncError) as ctx:
            read_sheet(self.service, ID)
        self.assertIn("no access", str(ctx.exception))

        del self.service.errors["get"]
        self.service.errors["values.get"] = FakeHttpError(400, {"error": {"message": "Unable to parse range"}})
        with self.assertRaises(ContactSyncError) as ctx:
            read_sheet(self.service, ID, cell_range="ZZZ")
        self.assertIn("range is not valid", str(ctx.exception))

        self.service.errors["values.get"] = ConnectionError("offline")
        with self.assertRaises(ContactSyncError) as ctx:
            read_sheet(self.service, ID)
        self.assertIn("internet", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
