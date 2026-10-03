"""Step 3: the validation report."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QTabWidget, QVBoxLayout, QWidget

from app.ui.state import AppState
from app.ui.widgets.common import (
    StatCard, fill_table, make_label, make_muted, make_table, make_title, primary_button, secondary_button,
)


class ValidationPage(QWidget):
    back_requested = Signal()
    next_requested = Signal()

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(14)
        root.addWidget(make_title("Validation"))
        root.addWidget(make_muted("A row is imported only if it has a name, a valid phone, a valid email and at least "
                                  "one label. Rows that fail are listed here and are not imported."))

        cards = QHBoxLayout()
        cards.setSpacing(12)
        self.total_card = StatCard("Rows read")
        self.valid_card = StatCard("Will be imported")
        self.rejected_card = StatCard("Rejected")
        self.duplicates_card = StatCard("Duplicates removed")
        for card in (self.total_card, self.valid_card, self.rejected_card, self.duplicates_card):
            cards.addWidget(card)
        root.addLayout(cards)

        self.tabs = QTabWidget()
        self.rejected_table = make_table()
        self.duplicates_table = make_table()
        self.tabs.addTab(self.rejected_table, "Rejected rows")
        self.tabs.addTab(self.duplicates_table, "Removed duplicates")
        root.addWidget(self.tabs, 1)

        self.note_label = make_label("", "warning", wrap=True)
        root.addWidget(self.note_label)

        bottom = QHBoxLayout()
        self.back_button = secondary_button("Back")
        self.back_button.clicked.connect(self.back_requested.emit)
        self.next_button = primary_button("Next: Import")
        self.next_button.clicked.connect(self.next_requested.emit)
        bottom.addWidget(self.back_button)
        bottom.addStretch(1)
        bottom.addWidget(self.next_button)
        root.addLayout(bottom)

    def refresh(self) -> None:
        result = self.state.result
        if result is None:
            return

        self.total_card.set_value(result.total_rows)
        self.valid_card.set_value(result.valid_count)
        self.rejected_card.set_value(result.rejected_count)
        self.duplicates_card.set_value(result.duplicate_count)

        fill_table(
            self.rejected_table,
            ["Row", "Name", "Phone", "Email", "Labels", "Reason"],
            [[r.row_number, r.name, r.phone, r.email, r.labels, "; ".join(r.reasons)] for r in result.rejected],
        )
        fill_table(
            self.duplicates_table,
            ["Row", "Kept row", "Name", "Phone", "Labels of the kept row"],
            [[d.row_number, d.kept_row_number, d.name, d.phone, ", ".join(d.labels)] for d in result.duplicates],
        )
        self.tabs.setTabText(0, f"Rejected rows ({result.rejected_count})")
        self.tabs.setTabText(1, f"Removed duplicates ({result.duplicate_count})")

        if result.valid_count == 0:
            self.note_label.setText("There are no valid rows to import. Go back and check the mapping.")
        elif result.duplicate_count:
            self.note_label.setText("Rows with the same phone were merged into the last one, and their labels were combined.")
        else:
            self.note_label.setText("")
        self.next_button.setEnabled(result.valid_count > 0)
