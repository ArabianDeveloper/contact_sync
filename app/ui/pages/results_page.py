"""Step 5: the results of the import."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QTabWidget, QVBoxLayout, QWidget

from app.ui import formatting
from app.ui.state import AppState
from app.ui.widgets.common import (
    StatCard, fill_table, make_label, make_muted, make_table, make_title, primary_button,
)


class ResultsPage(QWidget):
    new_import_requested = Signal()

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(14)
        root.addWidget(make_title("Results"))
        self.banner_label = make_label("", "success", wrap=True)
        root.addWidget(self.banner_label)

        cards = QHBoxLayout()
        cards.setSpacing(12)
        self.created_card = StatCard("Contacts created")
        self.existing_card = StatCard("Contacts already existing")
        self.labels_card = StatCard("Added to labels")
        self.spaces_card = StatCard("Added to spaces")
        self.failed_card = StatCard("Failed")
        for card in (self.created_card, self.existing_card, self.labels_card, self.spaces_card, self.failed_card):
            cards.addWidget(card)
        root.addLayout(cards)
        self.detail_label = make_muted("", wrap=True)
        root.addWidget(self.detail_label)

        self.tabs = QTabWidget()
        self.failed_table = make_table()
        self.reported_table = make_table()
        self.not_processed_table = make_table()
        self.tabs.addTab(self.failed_table, "Failed")
        self.tabs.addTab(self.reported_table, "Reported")
        self.tabs.addTab(self.not_processed_table, "Not processed")
        root.addWidget(self.tabs, 1)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self.new_button = primary_button("New import")
        self.new_button.clicked.connect(self.new_import_requested.emit)
        bottom.addWidget(self.new_button)
        root.addLayout(bottom)

    def refresh(self) -> None:
        summary = self.state.summary
        if summary is None:
            return

        style, text = formatting.banner(summary)
        self.banner_label.setObjectName(style)
        self.banner_label.setText(text)
        # the object name changed, so the stylesheet must be applied again
        self.banner_label.style().unpolish(self.banner_label)
        self.banner_label.style().polish(self.banner_label)

        self.created_card.set_value(summary.contacts_created)
        self.existing_card.set_value(summary.contacts_existing)
        self.labels_card.set_value(summary.added_to_labels)
        self.spaces_card.set_value(summary.added_to_spaces)
        self.failed_card.set_value(summary.failed_count)
        self.detail_label.setText(
            f"Rows processed: {summary.processed_rows} of {summary.total_rows}.   "
            f"Already in a label: {summary.already_in_labels}.   Already in a space: {summary.already_in_spaces}.   "
            f"Labels created: {summary.labels_created}.   Spaces created: {summary.spaces_created}."
        )

        fill_table(self.failed_table, ["Row", "Name", "Step", "Label / space", "Reason"],
                   formatting.failed_table(summary))
        fill_table(self.reported_table, ["Type", "Name", "Rows", "Row numbers", "Reason"],
                   formatting.reported_table(summary))
        fill_table(self.not_processed_table, ["Row"], formatting.not_processed_table(summary))
        self.tabs.setTabText(0, f"Failed ({summary.failed_count})")
        self.tabs.setTabText(1, f"Reported ({len(summary.reported_by_target())})")
        self.tabs.setTabText(2, f"Not processed ({len(summary.not_processed)})")
