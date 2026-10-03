"""Step 1: choose the data (a file or a Google Sheet), the tab and the header row, and see a preview."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLineEdit, QSpinBox, QVBoxLayout, QWidget,
)

from app.config import PREVIEW_ROWS
from app.core.readers import read_file
from app.ui.google_session import GoogleSession, read_google_sheet
from app.ui.state import AppState
from app.ui.widgets.common import (
    fill_table, make_label, make_muted, make_table, make_title, primary_button, secondary_button,
)
from app.ui.workers import run_in_background

FILE_FILTER = ("Data files (*.csv *.tsv *.txt *.xlsx *.xlsm *.xls *.ods *.json);;"
               "All files (*.*)")


class SourcePage(QWidget):
    changed = Signal()            # data was loaded or the header row changed
    next_requested = Signal()

    def __init__(self, state: AppState, session: GoogleSession):
        super().__init__()
        self.state = state
        self.session = session
        self._busy = False
        self._populating = False

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(14)
        root.addWidget(make_title("Source"))
        root.addWidget(make_muted("Choose a file with your contacts (CSV, TSV, XLSX, XLS, ODS, JSON), or paste a "
                                  "Google Sheet link. The type is detected automatically."))

        pick = QHBoxLayout()
        pick.setSpacing(10)
        self.choose_button = secondary_button("Choose file...")
        self.choose_button.clicked.connect(self.choose_file)
        self.path_label = make_muted("No file selected.", wrap=False)
        pick.addWidget(self.choose_button)
        pick.addWidget(self.path_label, 1)
        root.addLayout(pick)

        sheet_row = QHBoxLayout()
        sheet_row.setSpacing(10)
        self.sheet_edit = QLineEdit()
        self.sheet_edit.setPlaceholderText("Or paste a Google Sheet link or ID")
        self.sheet_edit.returnPressed.connect(self.load_google_sheet)
        self.sheet_button = secondary_button("Load Google Sheet")
        self.sheet_button.clicked.connect(self.load_google_sheet)
        sheet_row.addWidget(self.sheet_edit, 1)
        sheet_row.addWidget(self.sheet_button)
        root.addLayout(sheet_row)

        self.info_label = make_muted("", wrap=False)
        root.addWidget(self.info_label)

        options = QHBoxLayout()
        options.setSpacing(10)
        self.sheet_caption = make_label("Sheet")
        self.sheet_combo = QComboBox()
        self.sheet_combo.setMinimumWidth(200)
        self.sheet_combo.currentIndexChanged.connect(self._sheet_changed)
        self.range_caption = make_label("Range")
        self.range_edit = QLineEdit()
        self.range_edit.setPlaceholderText("A1:F200 (optional)")
        self.range_edit.setMaximumWidth(170)
        self.range_edit.returnPressed.connect(self._apply_range)
        self.range_button = secondary_button("Apply")
        self.range_button.clicked.connect(self._apply_range)
        self.header_spin = QSpinBox()
        self.header_spin.setRange(1, 1)
        self.header_spin.valueChanged.connect(self._header_row_changed)
        options.addWidget(self.sheet_caption)
        options.addWidget(self.sheet_combo)
        options.addSpacing(10)
        options.addWidget(self.range_caption)
        options.addWidget(self.range_edit)
        options.addWidget(self.range_button)
        options.addSpacing(10)
        options.addWidget(make_label("Header row"))
        options.addWidget(self.header_spin)
        options.addStretch(1)
        root.addLayout(options)

        self.preview_title = make_label("", "sectionTitle")
        root.addWidget(self.preview_title)
        self.table = make_table()
        root.addWidget(self.table, 1)

        self.error_label = make_label("", "error", wrap=True)
        root.addWidget(self.error_label)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self.next_button = primary_button("Next: Mapping")
        self.next_button.clicked.connect(self.next_requested.emit)
        bottom.addWidget(self.next_button)
        root.addLayout(bottom)

        self._show_empty()

    # ----------------------------------------------------------------- actions

    def choose_file(self) -> None:
        start = str(self.state.path.parent) if self.state.path else ""
        path, _ = QFileDialog.getOpenFileName(self, "Choose a data file", start, FILE_FILTER)
        if path:
            self._load_file(Path(path), None)

    def _load_file(self, path: Path, sheet: str | None) -> None:
        self._begin("Reading the file...")
        run_in_background(read_file, lambda table: self._file_loaded(path, table), self._load_failed,
                          path, sheet=sheet)

    def _file_loaded(self, path: Path, table) -> None:
        self.state.set_table(path, table)
        self._end()
        self._populate()
        self.changed.emit()

    def load_google_sheet(self) -> None:
        text = self.sheet_edit.text().strip()
        if not text:
            self.error_label.setText("Enter a Google Sheet link or ID.")
            return
        self.range_edit.setText("")
        self._load_sheet(text, None, "")

    def _apply_range(self) -> None:
        if self.state.source_kind != "gsheet" or self._busy:
            return
        self._load_sheet(self.state.source_text, self.sheet_combo.currentText() or None,
                         self.range_edit.text().strip())

    def _load_sheet(self, text: str, sheet: str | None, cell_range: str) -> None:
        self._begin("Reading the Google Sheet (you may be asked to sign in)...")
        run_in_background(
            read_google_sheet, lambda table: self._sheet_loaded(text, cell_range, table), self._load_failed,
            self.session, text, sheet, cell_range,
        )

    def _sheet_loaded(self, text: str, cell_range: str, table) -> None:
        self.state.set_google_table(text, table, cell_range)
        self._end()
        self._populate()
        self.changed.emit()

    def _load_failed(self, message: str) -> None:
        self._end()
        if self.state.table is not None:
            self._populate()               # show the previous data again
        self.error_label.setText(message)

    def _begin(self, text: str) -> None:
        self._busy = True
        self.error_label.setText("")
        self.info_label.setText(text)
        for widget in (self.choose_button, self.sheet_button, self.sheet_edit, self.sheet_combo,
                       self.range_button, self.range_edit, self.header_spin, self.next_button):
            widget.setEnabled(False)

    def _end(self) -> None:
        self._busy = False
        for widget in (self.choose_button, self.sheet_button, self.sheet_edit, self.sheet_combo,
                       self.range_button, self.range_edit):
            widget.setEnabled(True)
        has_table = self.state.table is not None
        self.header_spin.setEnabled(has_table)
        self.next_button.setEnabled(has_table)
        if not has_table:
            self.info_label.setText("")

    def _sheet_changed(self, index: int) -> None:
        if self._populating or self._busy or self.state.table is None or index < 0:
            return
        sheet = self.sheet_combo.currentText()
        if not sheet or sheet == self.state.table.sheet_name:
            return
        if self.state.source_kind == "gsheet":
            self._load_sheet(self.state.source_text, sheet, self.state.cell_range)
        elif self.state.path is not None:
            self._load_file(self.state.path, sheet)

    def _header_row_changed(self, value: int) -> None:
        if self._populating or self.state.table is None:
            return
        self.state.set_header_row(value - 1)
        self._fill_preview()
        self.changed.emit()

    # ------------------------------------------------------------------- views

    def _set_sheet_controls(self, sheets: bool, google: bool) -> None:
        self.sheet_caption.setVisible(sheets)
        self.sheet_combo.setVisible(sheets)
        self.range_caption.setVisible(google)
        self.range_edit.setVisible(google)
        self.range_button.setVisible(google)

    def _show_empty(self) -> None:
        self._populating = True
        try:
            self.path_label.setText("No file selected.")
            self.info_label.setText("")
            self.preview_title.setText("")
            self.error_label.setText("")
            self.sheet_combo.clear()
            self._set_sheet_controls(False, False)
            self.header_spin.setRange(1, 1)
            self.header_spin.setValue(1)
            self.header_spin.setEnabled(False)
            self.next_button.setEnabled(False)
            fill_table(self.table, [], [])
        finally:
            self._populating = False

    def _populate(self) -> None:
        table = self.state.table
        if table is None:
            self._show_empty()
            return
        self._populating = True
        try:
            google = self.state.source_kind == "gsheet"
            self.path_label.setText(f"Google Sheet: {table.source_name}" if google else str(self.state.path))
            parts = [f"Type: {'GOOGLE SHEET' if google else table.file_type.upper()}"]
            if table.encoding:
                parts.append(f"Encoding: {table.encoding}")
            if table.delimiter:
                parts.append(f"Delimiter: {'TAB' if table.delimiter == chr(9) else table.delimiter}")
            parts.append(f"Rows: {len(table.rows)}")
            self.info_label.setText("     ".join(parts))

            self._set_sheet_controls(bool(table.sheet_names), google)
            self.sheet_combo.clear()
            self.sheet_combo.addItems(table.sheet_names)
            if table.sheet_name:
                self.sheet_combo.setCurrentText(table.sheet_name)
            if google:
                self.range_edit.setText(self.state.cell_range)

            self.header_spin.setRange(1, max(1, len(table.rows)))
            self.header_spin.setValue(table.header_row + 1)
            self.header_spin.setEnabled(True)
            self.next_button.setEnabled(True)
        finally:
            self._populating = False
        self._fill_preview()

    def _fill_preview(self) -> None:
        table = self.state.table
        if table is None:
            return
        rows = table.preview(PREVIEW_ROWS)
        self.preview_title.setText(f"Preview (first {len(rows)} rows after the header)")
        fill_table(self.table, ["Row"] + table.headers(), [[number, *values] for number, values in rows])

    def refresh(self) -> None:
        """Called when the page is shown."""
        if not self._busy:
            self._populate()
