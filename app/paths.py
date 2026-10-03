"""Locations of the files the application stores in the user's AppData folder."""
from __future__ import annotations

import os
from pathlib import Path

from app.config import APP_DIR_NAME


def app_data_dir() -> Path:
    """%APPDATA%\\ContactSync (created if missing)."""
    base = os.environ.get("APPDATA")
    root = Path(base) if base else Path.home() / ".config"
    path = root / APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_path() -> Path:
    return app_data_dir() / "settings.json"


def profiles_path() -> Path:
    return app_data_dir() / "mapping_profiles.json"


def token_path() -> Path:
    return app_data_dir() / "token.json"


def logs_dir() -> Path:
    path = app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_file_path() -> Path:
    return logs_dir() / "contact_sync.log"
