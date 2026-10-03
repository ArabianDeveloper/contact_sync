"""Choose between several Google Chat spaces that have the same name (item 22)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QListWidget, QListWidgetItem, QVBoxLayout

from app.ui.formatting import describe_space
from app.ui.widgets.common import make_label, make_muted, primary_button, secondary_button


class SpaceChoiceDialog(QDialog):
    """After exec() returns Accepted, `chosen_space` is the space name chosen, or None if the
    user chose to skip this space."""

    def __init__(self, parent, label: str, spaces: list):
        super().__init__(parent)
        self.chosen_space: str | None = None
        self.setWindowTitle("Choose a space")
        self.setModal(True)
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)
        layout.addWidget(make_label(f"More than one space is named '{label.strip()}'", "sectionTitle"))
        layout.addWidget(make_muted("Choose the space that people with this label should be added to."))

        self.list = QListWidget()
        for space in spaces:
            item = QListWidgetItem(describe_space(space))
            item.setData(Qt.ItemDataRole.UserRole, space.name)
            self.list.addItem(item)
        skip = QListWidgetItem(f"Skip: do not add anyone to a space named '{label.strip()}'")
        skip.setData(Qt.ItemDataRole.UserRole, None)
        self.list.addItem(skip)
        layout.addWidget(self.list)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        buttons.addStretch(1)
        cancel = secondary_button("Cancel the import")
        cancel.clicked.connect(self.reject)
        self.ok_button = primary_button("OK")
        self.ok_button.setEnabled(False)
        self.ok_button.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(self.ok_button)
        layout.addLayout(buttons)

        self.list.currentRowChanged.connect(lambda row: self.ok_button.setEnabled(row >= 0))

    def accept(self) -> None:
        row = self.list.currentRow()
        if row < 0:
            return
        self.chosen_space = self.list.item(row).data(Qt.ItemDataRole.UserRole)
        super().accept()
