"""Run a function in a background thread and get the result back in the window thread."""
from __future__ import annotations

import logging
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from app.core.errors import ContactSyncError

logger = logging.getLogger("contact_sync.ui.workers")

_active: set["_Handle"] = set()    # keeps the handles alive until the task ends


class _Handle(QObject):
    """Lives in the window thread. The task emits its signals; the slots run in the window thread."""

    done = Signal(object)
    failed = Signal(str)

    def __init__(self, on_done: Callable[[Any], None], on_error: Callable[[str], None]):
        super().__init__()
        self._on_done = on_done
        self._on_error = on_error
        self.done.connect(self._handle_done)
        self.failed.connect(self._handle_failed)

    @Slot(object)
    def _handle_done(self, result):
        _active.discard(self)
        self._on_done(result)

    @Slot(str)
    def _handle_failed(self, message):
        _active.discard(self)
        self._on_error(message)


class _Task(QRunnable):
    def __init__(self, handle: _Handle, fn: Callable, args: tuple, kwargs: dict):
        super().__init__()
        self._handle = handle
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            result = self._fn(*self._args, **self._kwargs)
        except ContactSyncError as exc:
            self._handle.failed.emit(str(exc))
        except Exception as exc:  # never let a background error close the window
            logger.exception("Unexpected error in a background task (%s)", type(exc).__name__)
            self._handle.failed.emit(f"Unexpected error: {type(exc).__name__}. See the log file.")
        else:
            self._handle.done.emit(result)


def run_in_background(
    fn: Callable,
    on_done: Callable[[Any], None],
    on_error: Callable[[str], None],
    *args,
    **kwargs,
) -> None:
    """Run fn(*args, **kwargs) in a thread. on_done(result) or on_error(message) is called in the
    window thread. Call it from the window thread only."""
    handle = _Handle(on_done, on_error)
    _active.add(handle)
    QThreadPool.globalInstance().start(_Task(handle, fn, args, kwargs))
