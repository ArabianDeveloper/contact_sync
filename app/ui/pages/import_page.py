"""Step 4: confirm and run the import, with progress and a live log."""
from __future__ import annotations

import html

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QProgressBar, QTextEdit, QVBoxLayout, QWidget,
)

from app.runner.import_runner import ImportRunner, RunOptions
from app.ui.dialogs.confirm_import import ConfirmImportDialog
from app.ui.dialogs.space_choice import SpaceChoiceDialog
from app.ui.google_session import GoogleSession
from app.ui.state import AppState
from app.ui.theme import COLORS
from app.ui.widgets.common import (
    StatCard, make_label, make_muted, make_title, primary_button, secondary_button,
)
from app.ui.workers import run_in_background

_LOG_COLORS = {"info": COLORS["text"], "warning": COLORS["warning"], "error": COLORS["error"]}


class _RunBridge(QObject):
    """The runner works in a background thread. These signals bring its messages to the window."""

    progress = Signal(int, int)
    log = Signal(str, str)


class ImportPage(QWidget):
    back_requested = Signal()
    run_state_changed = Signal()      # an import started or ended
    finished = Signal()               # the import ended with a summary

    def __init__(self, state: AppState, session: GoogleSession):
        super().__init__()
        self.state = state
        self.session = session
        self._runner: ImportRunner | None = None
        self._chat = None
        self._rows: list = []
        self._cancel_requested = False

        self._bridge = _RunBridge()
        self._bridge.progress.connect(self._on_progress)
        self._bridge.log.connect(self._on_log)

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(14)
        root.addWidget(make_title("Import"))
        root.addWidget(make_muted("Check the numbers, then start. The program signs in to Google the first time "
                                  "it is needed (a browser window opens)."))

        cards = QHBoxLayout()
        cards.setSpacing(12)
        self.rows_card = StatCard("Rows to import")
        self.labels_card = StatCard("Distinct labels")
        self.rejected_card = StatCard("Rejected rows")
        self.duplicates_card = StatCard("Duplicates removed")
        for card in (self.rows_card, self.labels_card, self.rejected_card, self.duplicates_card):
            cards.addWidget(card)
        root.addLayout(cards)

        self.toggles_label = make_muted("", wrap=True)
        root.addWidget(self.toggles_label)

        self.status_label = make_label("", "sectionTitle")
        root.addWidget(self.status_label)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        root.addWidget(self.progress)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.document().setMaximumBlockCount(5000)
        root.addWidget(self.log, 1)

        self.error_label = make_label("", "error", wrap=True)
        root.addWidget(self.error_label)

        bottom = QHBoxLayout()
        bottom.setSpacing(10)
        self.back_button = secondary_button("Back")
        self.back_button.clicked.connect(self.back_requested.emit)
        self.cancel_button = secondary_button("Cancel import")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.request_cancel)
        self.start_button = primary_button("Start import")
        self.start_button.clicked.connect(self._start)
        bottom.addWidget(self.back_button)
        bottom.addStretch(1)
        bottom.addWidget(self.cancel_button)
        bottom.addWidget(self.start_button)
        root.addLayout(bottom)

    # -------------------------------------------------------------------- view

    def refresh(self) -> None:
        result = self.state.result
        if result is None or self.state.running:
            return
        self.rows_card.set_value(result.valid_count)
        self.labels_card.set_value(len(result.distinct_labels()))
        self.rejected_card.set_value(result.rejected_count)
        self.duplicates_card.set_value(result.duplicate_count)
        settings = self.state.settings
        self.toggles_label.setText(
            f"Create missing labels: {'On' if settings.auto_create_labels else 'Off'}.   "
            f"Create missing spaces: {'On' if settings.auto_create_spaces else 'Off'}.   "
            "(You can change this in Settings.)"
        )
        self.start_button.setEnabled(result.valid_count > 0)

    def _set_running(self, running: bool) -> None:
        self.state.running = running
        self.start_button.setEnabled(not running)
        self.back_button.setEnabled(not running)
        if not running:
            self.cancel_button.setEnabled(False)
        self.run_state_changed.emit()

    def _on_progress(self, done: int, total: int) -> None:
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(done)
        self.status_label.setText(f"Importing... {done} of {total} rows")

    def _on_log(self, level: str, text: str) -> None:
        color = _LOG_COLORS.get(level, COLORS["text"])
        self.log.append(f'<span style="color:{color}">{html.escape(text)}</span>')

    # --------------------------------------------------------------- the steps

    def _start(self) -> None:
        result = self.state.result
        if result is None or result.valid_count == 0 or self.state.running:
            return
        dialog = ConfirmImportDialog(self.window(), self.state.import_overview())
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self._rows = list(result.valid_rows)
        self._runner = None
        self._chat = None
        self._cancel_requested = False
        self.error_label.setText("")
        self.log.clear()
        self.status_label.setText("Connecting to Google...")
        self.progress.setRange(0, 0)                      # busy
        self._set_running(True)
        run_in_background(self.session.build_services, self._services_ready, self._failed)

    def _services_ready(self, services) -> None:
        contacts, chat = services
        if self._cancel_requested:
            self._aborted()
            return
        settings = self.state.settings
        self._chat = chat
        self._runner = ImportRunner(
            contacts, chat,
            RunOptions(create_labels=settings.auto_create_labels, create_spaces=settings.auto_create_spaces),
            on_progress=lambda done, total: self._bridge.progress.emit(done, total),
            on_log=lambda level, text: self._bridge.log.emit(level, text),
        )
        self.cancel_button.setEnabled(True)
        self.status_label.setText("Loading your labels, contacts and spaces from Google...")
        run_in_background(self._runner.prepare, self._prepared, self._failed, self._rows)

    def _prepared(self, duplicates) -> None:
        if self._cancel_requested:
            self._aborted()
            return
        for label, spaces in duplicates:
            dialog = SpaceChoiceDialog(self.window(), label, spaces)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                self._aborted()
                return
            self._chat.choose(label, dialog.chosen_space)
        self.progress.setRange(0, max(len(self._rows), 1))
        self.progress.setValue(0)
        self.status_label.setText(f"Importing... 0 of {len(self._rows)} rows")
        run_in_background(self._runner.run, self._finished, self._failed, self._rows)

    def _finished(self, summary) -> None:
        self.state.finish_run(summary)
        self._runner = None
        self.cancel_button.setEnabled(False)
        self.start_button.setEnabled(True)
        self.back_button.setEnabled(True)
        self.status_label.setText("")
        self.run_state_changed.emit()
        self.finished.emit()

    def _failed(self, message: str) -> None:
        if self._cancel_requested:                 # the user cancelled while Google was being loaded
            self._aborted()
            return
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.status_label.setText("")
        self.error_label.setText(message)
        self._runner = None
        self._set_running(False)

    def _aborted(self) -> None:
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.status_label.setText("The import was cancelled.")
        self._runner = None
        self._set_running(False)

    # ------------------------------------------------------------------ cancel

    @property
    def is_running(self) -> bool:
        return self.state.running

    def request_cancel(self) -> None:
        """Stop after the row in progress. Before the run starts, the import is abandoned."""
        self._cancel_requested = True
        self.cancel_button.setEnabled(False)
        self.status_label.setText("Cancelling after the current row...")
        if self._runner is not None:
            self._runner.cancel()
