"""Small widgets and helpers used by the pages."""
from __future__ import annotations

from typing import Iterable, Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QHeaderView, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout,
)

MAX_COLUMN_WIDTH = 320


def make_label(text: str = "", name: str | None = None, wrap: bool = False) -> QLabel:
    label = QLabel(text)
    if name:
        label.setObjectName(name)
    label.setWordWrap(wrap)
    return label


def make_title(text: str) -> QLabel:
    return make_label(text, "title")


def make_muted(text: str = "", wrap: bool = True) -> QLabel:
    return make_label(text, "muted", wrap)


def primary_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("primary")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def secondary_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


class StatCard(QFrame):
    """A number with a caption."""

    def __init__(self, caption: str, value: str = "-"):
        super().__init__()
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(2)
        self._value = make_label(value, "statValue")
        layout.addWidget(self._value)
        layout.addWidget(make_muted(caption, wrap=False))

    def set_value(self, value) -> None:
        self._value.setText(str(value))


def make_table() -> QTableWidget:
    table = QTableWidget()
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setAlternatingRowColors(True)
    table.setWordWrap(False)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setStretchLastSection(True)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    return table


def fill_table(table: QTableWidget, headers: Sequence[str], rows: Iterable[Sequence]) -> None:
    """Show the headers and rows (every value is shown as text)."""
    rows = list(rows)
    table.setUpdatesEnabled(False)
    try:
        table.clear()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels([str(h) for h in headers])
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                item = QTableWidgetItem("" if value is None else str(value))
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                table.setItem(r, c, item)
        table.resizeColumnsToContents()
        for c in range(len(headers)):
            if table.columnWidth(c) > MAX_COLUMN_WIDTH:
                table.setColumnWidth(c, MAX_COLUMN_WIDTH)
    finally:
        table.setUpdatesEnabled(True)
