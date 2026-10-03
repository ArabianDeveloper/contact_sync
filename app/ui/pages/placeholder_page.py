"""A page that is built in the next stage."""
from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from app.ui.widgets.common import make_muted, make_title


class PlaceholderPage(QWidget):
    def __init__(self, title: str, text: str):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(14)
        root.addWidget(make_title(title))
        root.addWidget(make_muted(text))
        root.addStretch(1)

    def refresh(self) -> None:
        pass
