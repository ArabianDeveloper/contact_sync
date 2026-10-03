import unittest

from app.core.dedupe import remove_duplicates
from app.core.models import CleanRow


def row(number, phone, labels, name="N"):
    return CleanRow(row_number=number, name=name, phone=phone, email="e@x.com", labels=labels)


class DedupeTests(unittest.TestCase):
    def test_no_duplicates(self):
        rows = [row(2, "+1", ["A"]), row(3, "+2", ["B"])]
        kept, dups = remove_duplicates(rows)
        self.assertEqual(kept, rows)
        self.assertEqual(dups, [])

    def test_last_row_is_kept_and_labels_are_merged(self):
        rows = [row(2, "+1", ["Team1"], "First"), row(3, "+2", ["X"]), row(4, "+1", ["Team2"], "Last")]
        kept, dups = remove_duplicates(rows)
        self.assertEqual([r.row_number for r in kept], [3, 4])          # file order
        last = kept[1]
        self.assertEqual(last.name, "Last")
        self.assertEqual(last.labels, ["Team1", "Team2"])
        self.assertEqual(len(dups), 1)
        self.assertEqual((dups[0].row_number, dups[0].kept_row_number), (2, 4))
        self.assertEqual(dups[0].name, "First")
        self.assertEqual(dups[0].labels, ["Team1", "Team2"])

    def test_repeated_labels_are_not_duplicated_and_three_rows(self):
        rows = [row(2, "+1", ["A", "B"]), row(3, "+1", ["b", "C"]), row(4, "+1", ["A"])]
        kept, dups = remove_duplicates(rows)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].row_number, 4)
        self.assertEqual(kept[0].labels, ["A", "B", "C"])
        self.assertEqual([d.row_number for d in dups], [2, 3])

    def test_input_rows_are_not_changed(self):
        original = row(2, "+1", ["A"])
        remove_duplicates([original, row(3, "+1", ["B"])])
        self.assertEqual(original.labels, ["A"])


if __name__ == "__main__":
    unittest.main()
