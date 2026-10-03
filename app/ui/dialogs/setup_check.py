"""The result of the setup check (item 43)."""
from __future__ import annotations

import html

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QVBoxLayout

from app.ui.theme import COLORS
from app.ui.widgets.common import make_label, make_muted, primary_button

_STATUS = {
    "ok": ("OK", COLORS["success"]),
    "fail": ("FAILED", COLORS["error"]),
    "warn": ("WARNING", COLORS["warning"]),
    "skipped": ("SKIPPED", COLORS["muted"]),
}


def result_html(result) -> str:
    """One line of the report as HTML."""
    text, color = _STATUS.get(result.status, ("?", COLORS["muted"]))
    line = (f'<span style="color:{color}"><b>{text}</b></span>&nbsp;&nbsp;'
            f'<b>{html.escape(result.title)}</b><br>{html.escape(result.message)}')
    if result.help_url:
        line += f'<br><a style="color:{COLORS["accent"]}" href="{html.escape(result.help_url)}">Open the link to fix it</a>'
    return line


class SetupCheckDialog(QDialog):
    def __init__(self, parent, results: list):
        super().__init__(parent)
        self.setWindowTitle("Setup check")
        self.setModal(True)
        self.setMinimumWidth(600)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(12)
        layout.addWidget(make_label("Setup check", "sectionTitle"))
        problems = [r for r in results if r.status in ("fail", "warn")]
        layout.addWidget(make_muted("Everything is ready." if not problems else "Some things need your attention."))

        for result in results:
            label = make_label(result_html(result), wrap=True)
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setOpenExternalLinks(True)
            layout.addWidget(label)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        close = primary_button("Close")
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)
