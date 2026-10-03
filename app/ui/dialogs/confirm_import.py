"""Confirmation before the real import (item 38)."""
from __future__ import annotations

from PySide6.QtWidgets import QDialog, QGridLayout, QHBoxLayout, QVBoxLayout

from app.ui.widgets.common import make_label, make_muted, primary_button, secondary_button


class ConfirmImportDialog(QDialog):
    """Shows the counts from the validation. exec() returns Accepted when the user starts."""

    def __init__(self, parent, items: list[tuple[str, str]]):
        super().__init__(parent)
        self.setWindowTitle("Start the import?")
        self.setModal(True)
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)
        layout.addWidget(make_label("Start the import?", "sectionTitle"))
        layout.addWidget(make_muted("This creates real contacts, labels and Google Chat spaces in your Google account."))

        grid = QGridLayout()
        grid.setHorizontalSpacing(28)
        grid.setVerticalSpacing(8)
        for row, (caption, value) in enumerate(items):
            grid.addWidget(make_muted(caption, wrap=False), row, 0)
            grid.addWidget(make_label(value), row, 1)
        layout.addLayout(grid)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        buttons.addStretch(1)
        cancel = secondary_button("Cancel")
        cancel.clicked.connect(self.reject)
        start = primary_button("Start import")
        start.clicked.connect(self.accept)
        start.setDefault(True)
        buttons.addWidget(cancel)
        buttons.addWidget(start)
        layout.addLayout(buttons)
