import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.core.errors import AuthError
from app.core.models import ItemResult, RunSummary
from app.core.pipeline import process_table
from app.core.readers import read_file
from app.core.readers.sheet_reader import read_sheet
from app.services import auth
from app.ui import formatting
from app.ui.google_session import GoogleSession, read_google_sheet
from app.ui.state import IMPORT, MAPPING, RESULTS, SOURCE, VALIDATION, AppState
from tests.fake_services import FakeChat, FakePeople, FakeSheets
from tests.fakes import patch_fake_libraries

SAMPLES = Path(__file__).parent / "sample_files"
ID = "1gXMz0Kj_t1FaoMyt2ygGjl9VTVfHuOHDzycycECefhQ"


class StateStage7Tests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(patch_fake_libraries().stop)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.state = AppState(Path(tmp.name) / "s.json", Path(tmp.name) / "p.json")
        path = SAMPLES / "contacts_utf8.csv"
        self.state.set_table(path, read_file(path))
        self.state.ensure_mapping()
        self.state.set_result(process_table(self.state.table, self.state.mapping))

    def test_overview(self):
        overview = dict(self.state.import_overview())
        self.assertEqual(overview["Rows read"], "4")
        self.assertEqual(overview["Rows to import"], "3")
        self.assertEqual(overview["Rejected rows (not imported)"], "1")
        self.assertEqual(overview["Distinct labels"], "3")
        self.assertEqual(overview["Create missing labels"], "On")
        self.state.update_settings(auto_create_spaces=False)
        self.assertEqual(dict(self.state.import_overview())["Create missing spaces"], "Off")

    def test_only_the_import_page_opens_while_running(self):
        s = self.state
        self.assertTrue(s.can_open(SOURCE) and s.can_open(MAPPING) and s.can_open(VALIDATION))
        s.running = True
        self.assertEqual([s.can_open(i) for i in range(6)], [False, False, False, True, False, False])

    def test_finish_run_opens_results(self):
        s = self.state
        s.running = True
        s.finish_run(RunSummary(total_rows=3))
        self.assertFalse(s.running)
        self.assertTrue(s.can_open(RESULTS))

    def test_reset_all_keeps_settings(self):
        s = self.state
        s.update_settings(auto_create_labels=False)
        s.finish_run(RunSummary())
        s.reset_all()
        self.assertIsNone(s.table)
        self.assertIsNone(s.result)
        self.assertIsNone(s.summary)
        self.assertFalse(s.can_open(MAPPING))
        self.assertFalse(s.settings.auto_create_labels)

    def test_google_sheet_source(self):
        s = self.state
        service = FakeSheets({"Sheet1": [["First", "Family", "Phone", "Email", "Labels"],
                                         ["Ali", "Khan", "99123456", "a@x.com", "Team1"]]})
        s.set_google_table(f"  {ID} ", read_sheet(service, ID), " A1:E10 ")
        self.assertEqual((s.source_kind, s.source_text, s.cell_range), ("gsheet", ID, "A1:E10"))
        self.assertIsNone(s.path)
        self.assertIsNone(s.result)
        s.ensure_mapping()
        self.assertTrue(s.mapping.is_complete())
        s.set_table(SAMPLES / "contacts_utf8.csv", read_file(SAMPLES / "contacts_utf8.csv"))
        self.assertEqual((s.source_kind, s.source_text), ("file", ""))


class FormattingTests(unittest.TestCase):
    def test_format_rows(self):
        self.assertEqual(format_rows := formatting.format_rows([2, 5]), "2, 5")
        self.assertEqual(formatting.format_rows(list(range(1, 31))).endswith("... (+10 more)"), True)

    def test_tables_and_banner(self):
        summary = RunSummary(total_rows=5, processed_rows=5)
        summary.failed.append(ItemResult(4, "Sara", "space", "Team1", "Google denied the request.", "permission"))
        summary.reported += [
            ItemResult(2, "Ali", "label", "Team9", "The label does not exist and auto-create labels is off."),
            ItemResult(3, "Omar", "label", "Team9", "The label does not exist and auto-create labels is off."),
        ]
        self.assertEqual(formatting.failed_table(summary), [[4, "Sara", "Space", "Team1", "Google denied the request."]])
        self.assertEqual(formatting.reported_table(summary),
                         [["Label", "Team9", 2, "2, 3", "The label does not exist and auto-create labels is off."]])
        self.assertEqual(formatting.banner(summary)[0], "warning")
        self.assertEqual(formatting.banner(RunSummary())[0], "success")
        cancelled = RunSummary(cancelled=True, not_processed=[7, 8])
        self.assertEqual(formatting.banner(cancelled), ("warning", "The import was cancelled. 2 rows were not processed."))
        self.assertEqual(formatting.not_processed_table(cancelled), [[7], [8]])
        stopped = RunSummary(stopped_reason="Sign in again.")
        self.assertEqual(formatting.banner(stopped), ("error", "The import was stopped: Sign in again."))


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        creds = object()
        self.creds = creds

        def get_credentials(path, token_path=None, login_if_needed=True):
            self.calls.append(("get", path, login_if_needed))
            if not login_if_needed:
                raise AuthError("not signed in")
            return creds

        patchers = [
            mock.patch.object(auth, "get_credentials", side_effect=get_credentials),
            mock.patch.object(auth, "load_credentials", return_value=None),
            mock.patch.object(auth, "build_people", return_value=FakePeople()),
            mock.patch.object(auth, "build_chat", return_value=FakeChat()),
            mock.patch.object(auth, "build_sheets", return_value=FakeSheets(
                {"Sheet1": [["Name", "Phone", "Email", "Labels"], ["Ali", "99123456", "a@x.com", "T"]]})),
        ]
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)
        self.session = GoogleSession(lambda: "C:\\credentials.json")

    def test_current_credentials_never_logs_in(self):
        self.assertIsNone(self.session.current_credentials())
        self.assertEqual(self.calls, [])

    def test_credentials_login_once_and_reset(self):
        self.assertIs(self.session.credentials(), self.creds)
        self.session.credentials()
        self.assertEqual(self.calls, [("get", "C:\\credentials.json", True)])
        self.session.reset()
        self.session.credentials()
        self.assertEqual(len(self.calls), 2)

    def test_services_and_sheet(self):
        contacts, chat = self.session.build_services()
        self.assertTrue(hasattr(contacts, "load_contacts") and hasattr(chat, "load_spaces"))
        table = read_google_sheet(self.session, ID)
        self.assertEqual(table.headers(), ["Name", "Phone", "Email", "Labels"])

    def test_login_error_is_raised(self):
        with mock.patch.object(auth, "get_credentials", side_effect=AuthError("bad credentials file")):
            with self.assertRaises(AuthError):
                self.session.credentials()


if __name__ == "__main__":
    unittest.main()
