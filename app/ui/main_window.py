"""The main window: sidebar with the steps and the pages."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QListWidget, QListWidgetItem, QMessageBox, QStackedWidget, QVBoxLayout, QWidget,
)

from app.config import APP_NAME, VERSION
from app.ui.google_session import GoogleSession
from app.ui.pages.import_page import ImportPage
from app.ui.pages.mapping_page import MappingPage
from app.ui.pages.results_page import ResultsPage
from app.ui.pages.settings_page import SettingsPage
from app.ui.pages.source_page import SourcePage
from app.ui.pages.validation_page import ValidationPage
from app.ui.state import (
    IMPORT, MAPPING, RESULTS, SETTINGS, SOURCE, STEP_TITLES, VALIDATION, AppState,
)
from app.ui.widgets.common import make_label

_ENABLED = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
_DISABLED = Qt.ItemFlag.NoItemFlags


class MainWindow(QWidget):
    def __init__(self, state: AppState, session: GoogleSession | None = None):
        super().__init__()
        self.state = state
        self.session = session or GoogleSession(lambda: state.settings.credentials_path)
        self._close_when_done = False
        self.setWindowTitle(f"{APP_NAME} {VERSION}")
        self.resize(1180, 780)
        self.setMinimumSize(940, 640)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # sidebar
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(230)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(0, 0, 0, 12)
        side_layout.setSpacing(0)
        side_layout.addWidget(make_label(APP_NAME, "brand"))
        self.steps = QListWidget()
        self.steps.setObjectName("steps")
        self.steps.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        labels = [f"{i + 1}   {title}" for i, title in enumerate(STEP_TITLES[:5])] + [STEP_TITLES[SETTINGS]]
        for text in labels:
            self.steps.addItem(QListWidgetItem(text))
        side_layout.addWidget(self.steps, 1)
        root.addWidget(sidebar)

        # pages (the order is the order of the steps)
        self.source_page = SourcePage(state, self.session)
        self.mapping_page = MappingPage(state)
        self.validation_page = ValidationPage(state)
        self.import_page = ImportPage(state, self.session)
        self.results_page = ResultsPage(state)
        self.settings_page = SettingsPage(state, self.session)

        self.pages = QStackedWidget()
        for page in (self.source_page, self.mapping_page, self.validation_page,
                     self.import_page, self.results_page, self.settings_page):
            self.pages.addWidget(page)
        root.addWidget(self.pages, 1)

        # navigation
        self.steps.currentRowChanged.connect(self._row_changed)
        self.source_page.changed.connect(self._refresh_sidebar)
        self.source_page.next_requested.connect(lambda: self.go_to(MAPPING))
        self.mapping_page.changed.connect(self._refresh_sidebar)
        self.mapping_page.back_requested.connect(lambda: self.go_to(SOURCE))
        self.mapping_page.validated.connect(lambda: self.go_to(VALIDATION))
        self.validation_page.back_requested.connect(lambda: self.go_to(MAPPING))
        self.validation_page.next_requested.connect(lambda: self.go_to(IMPORT))
        self.import_page.back_requested.connect(lambda: self.go_to(VALIDATION))
        self.import_page.run_state_changed.connect(self._run_state_changed)
        self.import_page.finished.connect(lambda: self.go_to(RESULTS))
        self.results_page.new_import_requested.connect(self._new_import)
        self.settings_page.changed.connect(self._refresh_sidebar)

        self._refresh_sidebar()
        self.steps.setCurrentRow(SOURCE)

    # -------------------------------------------------------------- navigation

    def go_to(self, step: int) -> None:
        self._refresh_sidebar()
        if self.state.can_open(step):
            self.steps.setCurrentRow(step)

    def _row_changed(self, row: int) -> None:
        if row < 0 or not self.state.can_open(row):
            return
        self.pages.setCurrentIndex(row)
        page = self.pages.currentWidget()
        if hasattr(page, "refresh"):
            page.refresh()
        self._refresh_sidebar()

    def _refresh_sidebar(self) -> None:
        """Enable only the steps that can be opened now."""
        for step in range(self.steps.count()):
            item = self.steps.item(step)
            item.setFlags(_ENABLED if self.state.can_open(step) else _DISABLED)

    def _new_import(self) -> None:
        self.state.reset_all()
        self._refresh_sidebar()
        self.steps.setCurrentRow(SOURCE)
        self.source_page.refresh()

    # ------------------------------------------------------------- the import

    def _run_state_changed(self) -> None:
        self._refresh_sidebar()
        if not self.state.running and self._close_when_done:
            self.close()

    def closeEvent(self, event) -> None:
        if self.state.running:
            answer = QMessageBox.question(
                self, "An import is running",
                "An import is running. Cancel it and close the program?\n\n"
                "The row in progress is finished first, then the program closes.",
            )
            if answer == QMessageBox.StandardButton.Yes:
                self._close_when_done = True
                self.import_page.request_cancel()
            event.ignore()
            return
        event.accept()
