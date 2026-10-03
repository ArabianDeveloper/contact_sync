import tempfile
import unittest
from pathlib import Path

from app.core.models import Mapping
from app.core.pipeline import process_table
from app.core.readers import read_file
from app.settings import load_settings
from app.ui.state import IMPORT, MAPPING, RESULTS, SETTINGS, SOURCE, VALIDATION, AppState
from tests.fakes import patch_fake_libraries

SAMPLES = Path(__file__).parent / "sample_files"


class StateTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(patch_fake_libraries().stop)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.settings_path = self.dir / "settings.json"
        self.profiles_path = self.dir / "profiles.json"
        self.state = AppState(self.settings_path, self.profiles_path)

    def load(self, name="contacts_utf8.csv"):
        path = SAMPLES / name
        self.state.set_table(path, read_file(path))

    def test_navigation_rules(self):
        s = self.state
        self.assertEqual([s.can_open(i) for i in (SOURCE, MAPPING, VALIDATION, IMPORT, RESULTS, SETTINGS)],
                         [True, False, False, False, False, True])
        self.load()
        self.assertTrue(s.can_open(MAPPING))
        self.assertFalse(s.can_open(VALIDATION))

        s.ensure_mapping()
        s.set_result(process_table(s.table, s.mapping, s.name_options()))
        self.assertTrue(s.can_open(VALIDATION))
        self.assertTrue(s.can_open(IMPORT))
        self.assertFalse(s.can_open(RESULTS))

    def test_no_valid_rows_blocks_import(self):
        s = self.state
        self.load()
        s.ensure_mapping()
        s.mapping.phone_column = 0          # the phone is mapped to a name column: every row is invalid
        s.set_result(process_table(s.table, s.mapping))
        self.assertEqual(s.result.valid_count, 0)
        self.assertTrue(s.can_open(VALIDATION))
        self.assertFalse(s.can_open(IMPORT))

    def test_mapping_is_suggested_once(self):
        s = self.state
        self.load()
        s.ensure_mapping()
        self.assertTrue(s.mapping.is_complete())
        self.assertFalse(s.mapping_from_profile)
        s.mapping.name_columns = [0]                 # the user changes it
        s.ensure_mapping()                           # visiting the page again must not reset it
        self.assertEqual(s.mapping.name_columns, [0])

    def test_profile_is_saved_and_used_next_time(self):
        s = self.state
        self.load()
        s.ensure_mapping()
        s.mapping.name_columns = [2, 0]              # a custom order
        s.save_current_profile()

        again = AppState(self.settings_path, self.profiles_path)
        again.set_table(SAMPLES / "contacts_utf8.csv", read_file(SAMPLES / "contacts_utf8.csv"))
        again.ensure_mapping()
        self.assertTrue(again.mapping_from_profile)
        self.assertEqual(again.mapping.name_columns, [2, 0])

    def test_incomplete_mapping_is_not_saved(self):
        s = self.state
        self.load()
        s.mapping = Mapping(name_columns=[0])
        s.save_current_profile()
        self.assertFalse(self.profiles_path.exists())

    def test_changing_the_header_row_or_file_clears_everything(self):
        s = self.state
        self.load("contacts_title_row.csv")
        self.assertEqual(s.table.header_row, 2)
        s.ensure_mapping()
        s.set_result(process_table(s.table, s.mapping))
        s.set_header_row(0)
        self.assertIsNone(s.result)
        self.assertFalse(s.mapping_ready)
        self.assertFalse(s.mapping.is_complete())
        self.assertFalse(s.can_open(VALIDATION))

        s.ensure_mapping()
        self.load()                                  # a new file
        self.assertFalse(s.mapping_ready)

    def test_invalidate_result(self):
        s = self.state
        self.load()
        s.ensure_mapping()
        s.set_result(process_table(s.table, s.mapping))
        s.invalidate_result()
        self.assertIsNone(s.result)
        self.assertTrue(s.mapping_ready)             # the mapping itself is kept

    def test_sample_preview(self):
        s = self.state
        self.assertEqual(s.sample_preview(), [])
        self.load()
        s.ensure_mapping()
        sample = s.sample_preview(5)
        self.assertEqual(len(sample), 4)
        self.assertEqual(sample[0].name, "Ahmed Salim Al Balushi")
        self.assertEqual(sample[0].phone, "+96899123456")
        self.assertEqual(sample[0].problems, "")
        self.assertEqual(sample[1].name, "محمد سالم العلوي")
        self.assertEqual(sample[3].problems, "Missing phone; Invalid email")
        self.assertEqual(len(s.sample_preview(2)), 2)

    def test_settings_are_saved_immediately(self):
        s = self.state
        s.update_settings(auto_create_spaces=False, credentials_path="C:\\x\\credentials.json", name_capitalize=False)
        saved = load_settings(self.settings_path)
        self.assertFalse(saved.auto_create_spaces)
        self.assertTrue(saved.auto_create_labels)
        self.assertEqual(saved.credentials_path, "C:\\x\\credentials.json")
        self.assertFalse(s.name_options().capitalize)

        reopened = AppState(self.settings_path, self.profiles_path)
        self.assertFalse(reopened.settings.auto_create_spaces)


if __name__ == "__main__":
    unittest.main()
