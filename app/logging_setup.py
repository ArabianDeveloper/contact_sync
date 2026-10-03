"""Log file in the AppData folder (rotating: 1 MB per file, 5 files).

The file log must not contain names, phone numbers or emails.
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from app import paths

LOGGER_NAME = "contact_sync"
_HANDLER_NAME = "contact_sync_file"


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    for handler in logger.handlers:
        if handler.get_name() == _HANDLER_NAME:
            return logger

    handler = RotatingFileHandler(
        paths.log_file_path(), maxBytes=1_000_000, backupCount=4, encoding="utf-8"
    )
    handler.set_name(_HANDLER_NAME)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
    return logger


def shutdown_logging() -> None:
    """Close and remove the file handler (used by the tests)."""
    logger = logging.getLogger(LOGGER_NAME)
    for handler in list(logger.handlers):
        if handler.get_name() == _HANDLER_NAME:
            handler.close()
            logger.removeHandler(handler)
