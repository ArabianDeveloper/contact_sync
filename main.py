"""Contact Sync entry point.

    python main.py          opens the window
    python main.py --info   prints where the data, settings and log files are
"""
from __future__ import annotations

import sys

from app import paths
from app.config import APP_NAME, VERSION
from app.logging_setup import setup_logging
from app.settings import load_settings, save_settings


def prepare():
    logger = setup_logging()
    settings = load_settings()
    if not paths.settings_path().exists():
        save_settings(settings)
    logger.info("%s %s started", APP_NAME, VERSION)
    return logger


def print_info() -> int:
    prepare()
    print(f"{APP_NAME} {VERSION}")
    print(f"Data folder   : {paths.app_data_dir()}")
    print(f"Settings file : {paths.settings_path()}")
    print(f"Log file      : {paths.log_file_path()}")
    return 0


def run_gui() -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("The library 'PySide6' is not installed. Run: pip install -r requirements.txt")
        return 1

    from app.ui.main_window import MainWindow
    from app.ui.state import AppState
    from app.ui.theme import apply_theme

    logger = prepare()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    apply_theme(app)

    window = MainWindow(AppState())
    window.show()
    logger.info("Window opened")
    return app.exec()


def main() -> int:
    if "--info" in sys.argv[1:]:
        return print_info()
    return run_gui()


if __name__ == "__main__":
    sys.exit(main())
