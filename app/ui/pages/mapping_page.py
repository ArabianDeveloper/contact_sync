"""Step 2: tell the program which column holds which field."""
from __future__ import annotations

import copy

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QGridLayout, QHBoxLayout, QListWidget, QListWidgetItem, QVBoxLayout, QWidget,
)

from app.core.pipeline import process_table
from app.ui.state import AppState
from app.ui.widgets.common import (
    fill_table, make_label, make_muted, make_table, make_title, primary_button, secondary_button,
)
from app.ui.workers import run_in_background

NOT_SELECTED = "- not selected -"


class MappingPage(QWidget):
    changed = Signal()
    back_requested = Signal()
    validated = Signal()          # the validation finished and the result is in the state

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self._loading = False
        self._busy = False

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(14)
        root.addWidget(make_title("Mapping"))
        root.addWidget(make_muted("Choose the column of each field. The name can be built from several columns, "
                                  "joined in the order of the list."))
        self.profile_label = make_label("", "success")
        root.addWidget(self.profile_label)

        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(10)

        # name columns
        grid.addWidget(make_label("Name columns", "sectionTitle"), 0, 0)
        name_box = QVBoxLayout()
        name_box.setSpacing(12)
        self.name_list = QListWidget()
        self.name_list.setMinimumHeight(110)
        self.name_list.setMaximumHeight(150)
        name_box.addWidget(self.name_list)
        add_row = QHBoxLayout()
        add_row.setSpacing(10)
        self.add_combo = QComboBox()
        self.add_button = secondary_button("Add")
        self.add_button.clicked.connect(self._add_name_column)
        add_row.addWidget(self.add_combo, 1)
        add_row.addWidget(self.add_button)
        name_box.addLayout(add_row)
        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        buttons.setContentsMargins(0, 6, 0, 0)
        self.remove_button = secondary_button("Remove")
        self.up_button = secondary_button("Move up")
        self.down_button = secondary_button("Move down")
        self.remove_button.clicked.connect(self._remove_name_column)
        self.up_button.clicked.connect(lambda: self._move_name_column(-1))
        self.down_button.clicked.connect(lambda: self._move_name_column(1))
        for button in (self.remove_button, self.up_button, self.down_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        name_box.addLayout(buttons)
        grid.addLayout(name_box, 0, 1)

        # single columns
        self.phone_combo = QComboBox()
        self.email_combo = QComboBox()
        self.labels_combo = QComboBox()
        for row, (caption, combo) in enumerate(
            (("Phone", self.phone_combo), ("Email", self.email_combo), ("Labels", self.labels_combo)), start=1
        ):
            grid.addWidget(make_label(caption, "sectionTitle"), row, 0)
            grid.addWidget(combo, row, 1)
            combo.currentIndexChanged.connect(self._store)
        grid.setColumnStretch(1, 1)
        root.addLayout(grid)

        # name cleanup
        cleanup = QHBoxLayout()
        cleanup.addWidget(make_label("English name cleanup", "sectionTitle"))
        self.trim_check = QCheckBox("Trim spaces")
        self.collapse_check = QCheckBox("Remove extra spaces")
        self.capitalize_check = QCheckBox("Capitalize")
        for check, key in ((self.trim_check, "name_trim"), (self.collapse_check, "name_collapse_spaces"),
                           (self.capitalize_check, "name_capitalize")):
            check.toggled.connect(lambda checked, key=key: self._cleanup_changed(key, checked))
            cleanup.addWidget(check)
        cleanup.addStretch(1)
        root.addLayout(cleanup)
        root.addWidget(make_muted("Names that contain Arabic letters are never changed."))

        root.addWidget(make_label("Sample: the first rows as they will be imported", "sectionTitle"))
        self.sample_table = make_table()
        self.sample_table.setMinimumHeight(190)
        root.addWidget(self.sample_table, 1)

        self.status_label = make_label("", "warning", wrap=True)
        root.addWidget(self.status_label)

        bottom = QHBoxLayout()
        self.back_button = secondary_button("Back")
        self.back_button.clicked.connect(self.back_requested.emit)
        self.next_button = primary_button("Next: Validation")
        self.next_button.clicked.connect(self._next)
        bottom.addWidget(self.back_button)
        bottom.addStretch(1)
        bottom.addWidget(self.next_button)
        root.addLayout(bottom)

    # ------------------------------------------------------------------- state

    def refresh(self) -> None:
        """Called when the page is shown: fill the widgets from the state."""
        state = self.state
        if state.table is None:
            return
        state.ensure_mapping()
        headers = state.headers()
        mapping = state.mapping

        self._loading = True
        try:
            self.add_combo.clear()
            for index, header in enumerate(headers):
                self.add_combo.addItem(f"{index + 1}. {header}", index)

            self.name_list.clear()
            for index in mapping.name_columns:
                self._append_name_item(index, headers)

            for combo, selected in ((self.phone_combo, mapping.phone_column),
                                    (self.email_combo, mapping.email_column),
                                    (self.labels_combo, mapping.labels_column)):
                combo.clear()
                combo.addItem(NOT_SELECTED, None)
                for index, header in enumerate(headers):
                    combo.addItem(f"{index + 1}. {header}", index)
                combo.setCurrentIndex(0 if selected is None else combo.findData(selected))

            settings = state.settings
            self.trim_check.setChecked(settings.name_trim)
            self.collapse_check.setChecked(settings.name_collapse_spaces)
            self.capitalize_check.setChecked(settings.name_capitalize)
        finally:
            self._loading = False

        self.profile_label.setText("Mapping loaded from a saved profile." if state.mapping_from_profile else "")
        self._update_view()

    def _append_name_item(self, index: int, headers: list[str]) -> None:
        item = QListWidgetItem(f"{index + 1}. {headers[index]}")
        item.setData(Qt.ItemDataRole.UserRole, index)
        self.name_list.addItem(item)

    def _store(self, *_args) -> None:
        """Copy the widgets into the state (every change)."""
        if self._loading:
            return
        mapping = self.state.mapping
        mapping.name_columns = [
            self.name_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.name_list.count())
        ]
        mapping.phone_column = self.phone_combo.currentData()
        mapping.email_column = self.email_combo.currentData()
        mapping.labels_column = self.labels_combo.currentData()
        self.state.mapping_from_profile = False
        self.profile_label.setText("")
        self.state.invalidate_result()
        self._update_view()
        self.changed.emit()

    def _cleanup_changed(self, key: str, checked: bool) -> None:
        if self._loading:
            return
        self.state.update_settings(**{key: checked})
        self.state.invalidate_result()
        self._update_view()
        self.changed.emit()

    def _update_view(self) -> None:
        mapping = self.state.mapping
        complete = mapping.is_complete()
        self.next_button.setEnabled(complete and not self._busy)

        missing = []
        if not mapping.name_columns:
            missing.append("name")
        if mapping.phone_column is None:
            missing.append("phone")
        if mapping.email_column is None:
            missing.append("email")
        if mapping.labels_column is None:
            missing.append("labels")
        self.status_label.setText("Still needed: " + ", ".join(missing) + "." if missing else "")

        samples = self.state.sample_preview(5)
        fill_table(
            self.sample_table,
            ["Row", "Name", "Phone", "Email", "Labels", "Problems"],
            [[s.row_number, s.name, s.phone, s.email, s.labels, s.problems] for s in samples],
        )

    # ----------------------------------------------------------- name columns

    def _add_name_column(self) -> None:
        index = self.add_combo.currentData()
        if index is None:
            return
        present = {self.name_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.name_list.count())}
        if index in present:
            return
        self._append_name_item(index, self.state.headers())
        self._store()

    def _remove_name_column(self) -> None:
        row = self.name_list.currentRow()
        if row >= 0:
            self.name_list.takeItem(row)
            self._store()

    def _move_name_column(self, step: int) -> None:
        row = self.name_list.currentRow()
        target = row + step
        if row < 0 or target < 0 or target >= self.name_list.count():
            return
        item = self.name_list.takeItem(row)
        self.name_list.insertItem(target, item)
        self.name_list.setCurrentRow(target)
        self._store()

    # -------------------------------------------------------------------- next

    def _next(self) -> None:
        state = self.state
        if not state.mapping.is_complete() or self._busy:
            return
        state.save_current_profile()
        self._busy = True
        self.next_button.setEnabled(False)
        self.next_button.setText("Validating...")
        run_in_background(
            process_table, self._validated, self._validation_failed,
            state.table, copy.deepcopy(state.mapping), state.name_options(),
        )

    def _validated(self, result) -> None:
        self._busy = False
        self.next_button.setText("Next: Validation")
        self.state.set_result(result)
        self._update_view()
        self.validated.emit()

    def _validation_failed(self, message: str) -> None:
        self._busy = False
        self.next_button.setText("Next: Validation")
        self.status_label.setText(message)
        self._update_view()
