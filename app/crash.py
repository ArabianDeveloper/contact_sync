"""Unexpected errors: write them to the log file and tell the user (the .exe has no console)."""
from __future__ import annotations

import logging
import sys
import traceback

from app import paths
from app.config import APP_NAME


def format_crash(exc_type, tb) -> str:
    """The error type and the code lines. The error message is left out because it can contain
    names, phone numbers or emails, and the log file must not contain them."""
    return f"{exc_type.__name__}\n" + "".join(traceback.format_tb(tb))


def install_excepthook(logger: logging.Logger) -> None:
    def hook(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        logger.critical("Unhandled error: %s", format_crash(exc_type, tb))
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox

            if QApplication.instance() is not None:
                QMessageBox.critical(
                    None, APP_NAME,
                    f"An unexpected error happened ({exc_type.__name__}).\n\n"
                    f"The details were saved in the log file:\n{paths.log_file_path()}",
                )
        except Exception:
            pass

    sys.excepthook = hook
