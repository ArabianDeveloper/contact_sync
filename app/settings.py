"""Application settings, saved in settings.json (the user data file)."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from app import paths

logger = logging.getLogger("contact_sync.settings")

_BOOL_FIELDS = (
    "auto_create_labels",
    "auto_create_spaces",
    "name_trim",
    "name_collapse_spaces",
    "name_capitalize",
)


@dataclass
class Settings:
    credentials_path: str | None = None
    auto_create_labels: bool = True
    auto_create_spaces: bool = True
    name_trim: bool = True
    name_collapse_spaces: bool = True
    name_capitalize: bool = True


def load_settings(path: Path | None = None) -> Settings:
    """Read the settings. Missing, unreadable or invalid values fall back to the defaults."""
    path = Path(path) if path else paths.settings_path()
    settings = Settings()
    if not path.exists():
        return settings

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("Settings file could not be read, defaults are used (%s)", type(exc).__name__)
        return settings

    if not isinstance(data, dict):
        logger.warning("Settings file has an invalid structure, defaults are used")
        return settings

    for name in _BOOL_FIELDS:
        value = data.get(name)
        if isinstance(value, bool):
            setattr(settings, name, value)

    credentials = data.get("credentials_path")
    if isinstance(credentials, str) and credentials.strip():
        settings.credentials_path = credentials

    return settings


def save_settings(settings: Settings, path: Path | None = None) -> None:
    """Write the settings (through a temporary file so a crash cannot corrupt them)."""
    path = Path(path) if path else paths.settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)
