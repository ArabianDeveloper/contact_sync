"""A line at the top of the window that tells the user a newer version exists."""
from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFrame, QHBoxLayout

from app.config import VERSION
from app.ui.widgets.common import make_label, primary_button, secondary_button


class UpdateBanner(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("banner")
        self._url: str | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 10, 24, 10)
        layout.setSpacing(10)
        self.label = make_label("", wrap=False)
        self.open_button = primary_button("Open the download page")
        self.open_button.clicked.connect(self._open)
        self.dismiss_button = secondary_button("Later")
        self.dismiss_button.clicked.connect(lambda: self.setVisible(False))
        layout.addWidget(self.label, 1)
        layout.addWidget(self.open_button)
        layout.addWidget(self.dismiss_button)
        self.setVisible(False)

    def show_update(self, info) -> None:
        """`info` has `version` and `url` (see app.update_check.UpdateInfo). None hides the banner."""
        if info is None:
            self.setVisible(False)
            return
        self._url = info.url
        self.label.setText(f"A new version is available: {info.version} (you are using {VERSION}).")
        self.setVisible(True)

    def _open(self) -> None:
        if self._url:
            QDesktopServices.openUrl(QUrl(self._url))
