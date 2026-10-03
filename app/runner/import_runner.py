"""The import job: loads the Google data, then processes the valid rows one by one.

It has no window code. The window will run it in a background thread and connect
`on_progress` and `on_log` to the progress bar and the live log.

Order:  prepare()  ->  (the window asks the user to choose between spaces with the same
name)  ->  run().
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Callable

from app.core.errors import AuthError, ContactSyncError
from app.core.models import (
    STEP_CONTACT, STEP_LABEL, STEP_SPACE, CleanRow, ItemResult, RunSummary,
)
from app.services import chat as chat_module
from app.services import contacts as contacts_module
from app.services.chat import ChatService, DuplicateSpaceError, SpaceInfo
from app.services.contacts import ContactsService
from app.services.errors import NETWORK, describe_error

logger = logging.getLogger("contact_sync.runner")

INFO, WARNING, ERROR = "info", "warning", "error"


class RunCancelled(ContactSyncError):
    """The user cancelled while the Google data was being loaded."""


@dataclass
class RunOptions:
    create_labels: bool = True
    create_spaces: bool = True
    max_network_failures: int = 5     # the run stops after this many network failures in a row


class ImportRunner:
    def __init__(
        self,
        contacts: ContactsService,
        chat: ChatService,
        options: RunOptions | None = None,
        on_progress: Callable[[int, int], None] | None = None,
        on_log: Callable[[str, str], None] | None = None,
    ):
        self._contacts = contacts
        self._chat = chat
        self._options = options or RunOptions()
        self._on_progress = on_progress
        self._on_log = on_log
        self._cancel = threading.Event()
        self._prepared = False
        self._network_streak = 0
        self._stop_reason: str | None = None

    # ------------------------------------------------------------------ control

    def cancel(self) -> None:
        """Ask the run to stop. The row being processed is finished first."""
        self._cancel.set()

    # ------------------------------------------------------------------ prepare

    def prepare(self, rows: list[CleanRow]) -> list[tuple[str, list[SpaceInfo]]]:
        """Load the labels, the contacts and the spaces from Google.

        Returns the labels that match more than one space. The user must choose one space
        for each of them (chat.choose) before run() is called.
        Raises ContactSyncError with a readable message if Google cannot be read.
        """
        steps = (
            ("labels", self._contacts.load_labels),
            ("contacts", lambda: self._contacts.load_contacts(
                lambda n: self._log(INFO, f"  {n} contacts read..."))),
            ("spaces", self._chat.load_spaces),
        )
        for name, load in steps:
            if self._cancel.is_set():
                raise RunCancelled("The import was cancelled.")
            self._log(INFO, f"Loading {name} from Google...")
            try:
                load()
            except ContactSyncError:
                raise
            except Exception as exc:
                logger.warning("Loading %s failed (%s)", name, describe_error(exc).kind)
                raise ContactSyncError(f"Loading the {name} failed. {describe_error(exc).message}") from exc

        self._prepared = True
        return self._chat.unresolved_duplicates(self._all_labels(rows))

    # ---------------------------------------------------------------------- run

    def run(self, rows: list[CleanRow]) -> RunSummary:
        if not self._prepared:
            raise RuntimeError("prepare() must be called before run().")
        unresolved = self._chat.unresolved_duplicates(self._all_labels(rows))
        if unresolved:
            raise DuplicateSpaceError(
                "Choose a space for: " + ", ".join(label for label, _ in unresolved)
            )

        summary = RunSummary(total_rows=len(rows))
        self._log(INFO, f"Importing {len(rows)} rows...")

        for index, row in enumerate(rows):
            if self._cancel.is_set():
                summary.cancelled = True
                summary.not_processed = [r.row_number for r in rows[index:]]
                self._log(WARNING, "Cancelled by the user.")
                break

            self._process_row(row, summary)
            summary.processed_rows += 1
            if self._on_progress:
                self._on_progress(summary.processed_rows, summary.total_rows)

            if self._stop_reason:
                summary.stopped_reason = self._stop_reason
                summary.not_processed = [r.row_number for r in rows[index + 1:]]
                self._log(ERROR, f"Stopped: {self._stop_reason}")
                break

        logger.info(
            "Run finished: processed=%d/%d, created=%d, existing=%d, labels=%d, spaces=%d, failed=%d, "
            "reported=%d, cancelled=%s, stopped=%s",
            summary.processed_rows, summary.total_rows, summary.contacts_created, summary.contacts_existing,
            summary.added_to_labels, summary.added_to_spaces, summary.failed_count, len(summary.reported),
            summary.cancelled, summary.stopped,
        )
        return summary

    # ---------------------------------------------------------------- one row

    def _process_row(self, row: CleanRow, summary: RunSummary) -> None:
        who = f"Row {row.row_number} ({row.name})"

        contact = self._contacts.find(row.phone)
        if contact is not None:
            summary.contacts_existing += 1
            self._log(INFO, f"{who}: contact already exists")
        else:
            try:
                contact = self._contacts.create_contact(row.name, row.phone, row.email)
            except Exception as exc:
                self._failed(summary, row, STEP_CONTACT, None, exc)
                return
            summary.contacts_created += 1
            self._network_streak = 0
            self._log(INFO, f"{who}: contact created")

        for label in row.labels:
            if self._stop_reason:
                return
            self._label_step(summary, row, contact, label)
            if self._stop_reason:
                return
            self._space_step(summary, row, label)

    def _label_step(self, summary: RunSummary, row: CleanRow, contact, label: str) -> None:
        who = f"Row {row.row_number} ({row.name})"
        try:
            ref = self._contacts.ensure_label(label, self._options.create_labels)
            if ref is None:
                self._reported(summary, row, STEP_LABEL, label, "The label does not exist and auto-create labels is off.")
                return
            if ref.created:
                summary.labels_created += 1
                self._network_streak = 0
                self._log(INFO, f"{who}: label '{label}' created")
            status = self._contacts.add_to_label(contact, ref.resource_name)
        except Exception as exc:
            self._failed(summary, row, STEP_LABEL, label, exc)
            return

        if status == contacts_module.ADDED:
            summary.added_to_labels += 1
            self._network_streak = 0
            self._log(INFO, f"{who}: added to label '{label}'")
        else:
            summary.already_in_labels += 1
            self._log(INFO, f"{who}: already in label '{label}'")

    def _space_step(self, summary: RunSummary, row: CleanRow, label: str) -> None:
        who = f"Row {row.row_number} ({row.name})"
        try:
            ref = self._chat.ensure_space(label, self._options.create_spaces)
            if ref is None:
                if self._chat.was_skipped(label):
                    message = "The space was skipped by your choice."
                else:
                    message = "The space does not exist and auto-create spaces is off."
                self._reported(summary, row, STEP_SPACE, label, message)
                return
            if ref.created:
                summary.spaces_created += 1
                self._network_streak = 0
                self._log(INFO, f"{who}: space '{label}' created")
            status = self._chat.add_member(ref.name, row.email)
        except Exception as exc:
            self._failed(summary, row, STEP_SPACE, label, exc)
            return

        self._network_streak = 0
        if status == chat_module.ADDED:
            summary.added_to_spaces += 1
            self._log(INFO, f"{who}: added to space '{label}'")
        else:
            summary.already_in_spaces += 1
            self._log(INFO, f"{who}: already in space '{label}'")

    # ----------------------------------------------------------- problems

    def _reported(self, summary: RunSummary, row: CleanRow, step: str, target: str, message: str) -> None:
        summary.reported.append(ItemResult(row.row_number, row.name, step, target, message))
        self._log(WARNING, f"Row {row.row_number} ({row.name}): {step} '{target}' reported: {message}")
        logger.info("Row %d: %s reported", row.row_number, step)

    def _failed(self, summary: RunSummary, row: CleanRow, step: str, target: str | None, exc: Exception) -> None:
        if isinstance(exc, ContactSyncError):
            message, kind, fatal = str(exc), "other", isinstance(exc, AuthError)
        else:
            info = describe_error(exc)
            message, kind, fatal = info.message, info.kind, info.is_fatal

        summary.failed.append(ItemResult(row.row_number, row.name, step, target, message, kind))
        place = f"{step} '{target}'" if target else step
        self._log(ERROR, f"Row {row.row_number} ({row.name}): {place} failed: {message}")
        logger.warning("Row %d: %s failed (%s)", row.row_number, step, kind)   # no personal data in the file log

        if kind == NETWORK:
            self._network_streak += 1
            if self._network_streak >= self._options.max_network_failures:
                self._stop_reason = (
                    f"Stopped after {self._options.max_network_failures} network failures in a row. "
                    "Check the internet connection and try again."
                )
        else:
            self._network_streak = 0

        if fatal:
            self._stop_reason = message

    @staticmethod
    def _all_labels(rows: list[CleanRow]) -> list[str]:
        return [label for row in rows for label in row.labels]

    def _log(self, level: str, text: str) -> None:
        if self._on_log:
            self._on_log(level, text)
