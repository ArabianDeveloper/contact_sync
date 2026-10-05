"""Settings: credentials.json, Google account, auto-create toggles, version."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QFileDialog, QHBoxLayout, QLineEdit, QMessageBox, QVBoxLayout, QWidget,
)

from app.config import APP_NAME, VERSION
from app.services import auth
from app.services.setup_check import run_setup_check
from app.ui.dialogs.setup_check import SetupCheckDialog
from app.ui.google_session import GoogleSession
from app.ui.state import AppState
from app.ui.widgets.common import make_label, make_muted, make_title, primary_button, scrollable, secondary_button
from app.ui.workers import run_in_background


def _restyle(label) -> None:
    """The object name of a label changed, so the stylesheet must be applied again."""
    label.style().unpolish(label)
    label.style().polish(label)


class SettingsPage(QWidget):
    changed = Signal()

    def __init__(self, state: AppState, session: GoogleSession):
        super().__init__()
        self.state = state
        self.session = session
        self._loading = False
        self._busy = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        content = QWidget()
        outer.addWidget(scrollable(content))
        root = QVBoxLayout(content)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(14)
        root.addWidget(make_title("Settings"))
        root.addWidget(make_muted("Settings are saved automatically."))

        # credentials
        root.addWidget(make_label("Google credentials", "sectionTitle"))
        root.addWidget(make_muted("Choose the credentials.json file of your Google Cloud project "
                                  "(an OAuth client of type 'Desktop app')."))
        row = QHBoxLayout()
        row.setSpacing(10)
        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("No credentials.json selected")
        self.browse_button = secondary_button("Choose file...")
        self.browse_button.clicked.connect(self._browse)
        row.addWidget(self.path_edit, 1)
        row.addWidget(self.browse_button)
        root.addLayout(row)
        self.credentials_status = make_label("", wrap=True)
        root.addWidget(self.credentials_status)

        # account
        root.addSpacing(8)
        root.addWidget(make_label("Google account", "sectionTitle"))
        self.account_status = make_label("", wrap=True)
        root.addWidget(self.account_status)
        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.sign_in_button = primary_button("Sign in")
        self.check_button = secondary_button("Run setup check")
        self.delete_button = secondary_button("Delete token")
        self.sign_in_button.clicked.connect(self._sign_in)
        self.check_button.clicked.connect(self._run_check)
        self.delete_button.clicked.connect(self._delete_token)
        for button in (self.sign_in_button, self.check_button, self.delete_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        root.addLayout(buttons)
        root.addWidget(make_muted("Delete the token to sign in with another Google account. "
                                  "You will be asked to sign in again the next time Google is needed."))
        self.message_label = make_label("", wrap=True)
        root.addWidget(self.message_label)

        # auto-create
        root.addSpacing(8)
        root.addWidget(make_label("Auto-create", "sectionTitle"))
        self.labels_check = QCheckBox("Create a contact label when it does not exist")
        self.spaces_check = QCheckBox("Create a Google Chat space when it does not exist")
        self.labels_check.toggled.connect(lambda checked: self._toggle("auto_create_labels", checked))
        self.spaces_check.toggled.connect(lambda checked: self._toggle("auto_create_spaces", checked))
        root.addWidget(self.labels_check)
        root.addWidget(self.spaces_check)
        root.addWidget(make_muted("When a toggle is off, a missing label or space is reported and not created. "
                                  "The contact is still added to the other labels and spaces."))

        root.addStretch(1)
        root.addWidget(make_muted(f"{APP_NAME} {VERSION}", wrap=False))

    # ------------------------------------------------------------------- view

    def refresh(self) -> None:
        settings = self.state.settings
        self._loading = True
        try:
            self.labels_check.setChecked(settings.auto_create_labels)
            self.spaces_check.setChecked(settings.auto_create_spaces)
        finally:
            self._loading = False
        self.path_edit.setText(settings.credentials_path or "")
        self._show_credentials_status()
        self._show_account_status()

    def _show_credentials_status(self) -> None:
        path = self.state.settings.credentials_path
        if not path:
            self.credentials_status.setObjectName("muted")
            self.credentials_status.setText("")
        else:
            ok, message = auth.credentials_file_status(path)
            self.credentials_status.setObjectName("success" if ok else "error")
            self.credentials_status.setText(message)
        _restyle(self.credentials_status)

    def _show_account_status(self) -> None:
        if auth.token_exists():
            self.account_status.setObjectName("success")
            self.account_status.setText("A Google sign-in is saved on this computer.")
        else:
            self.account_status.setObjectName("muted")
            self.account_status.setText("Not signed in. You are asked to sign in the first time Google is needed.")
        _restyle(self.account_status)

    def _message(self, text: str, style: str = "muted") -> None:
        self.message_label.setObjectName(style)
        self.message_label.setText(text)
        _restyle(self.message_label)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        for button in (self.sign_in_button, self.check_button, self.delete_button, self.browse_button):
            button.setEnabled(not busy)

    # ---------------------------------------------------------------- actions

    def _browse(self) -> None:
        current = self.state.settings.credentials_path
        start = str(Path(current).parent) if current else ""
        path, _ = QFileDialog.getOpenFileName(self, "Choose credentials.json", start,
                                              "JSON files (*.json);;All files (*.*)")
        if path:
            self.state.update_settings(credentials_path=path)
            self.refresh()
            self.changed.emit()

    def _toggle(self, key: str, checked: bool) -> None:
        if self._loading:
            return
        self.state.update_settings(**{key: checked})
        self.changed.emit()

    def _sign_in(self) -> None:
        ok, message = auth.credentials_file_status(self.state.settings.credentials_path)
        if not ok:
            self._message(message, "error")
            return
        self._message("A browser window opens. Sign in and allow every permission...")
        self._set_busy(True)
        run_in_background(self._sign_in_job, self._check_done, self._google_failed)

    def _sign_in_job(self):
        creds = self.session.credentials(login=True)
        return run_setup_check(self.state.settings.credentials_path, creds)

    def _run_check(self) -> None:
        self._message("Checking...")
        self._set_busy(True)
        run_in_background(self._check_job, self._check_done, self._google_failed)

    def _check_job(self):
        return run_setup_check(self.state.settings.credentials_path, self.session.current_credentials())

    def _check_done(self, results) -> None:
        self._set_busy(False)
        self._message("")
        self._show_account_status()
        SetupCheckDialog(self.window(), results).exec()

    def _google_failed(self, message: str) -> None:
        self._set_busy(False)
        self._show_account_status()
        self._message(message, "error")

    def _delete_token(self) -> None:
        if not auth.token_exists():
            self._message("There is no saved sign-in.")
            return
        answer = QMessageBox.question(
            self, "Delete the token",
            "Delete the saved Google sign-in?\n\nYou will be asked to sign in again the next time Google is needed.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            auth.delete_token()
        except Exception as exc:
            self._message(str(exc), "error")
            return
        self.session.reset()
        self._show_account_status()
        self._message("The token was deleted.", "success")
