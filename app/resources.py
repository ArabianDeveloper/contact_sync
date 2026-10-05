"""Finds files that are shipped with the program (the icon), in a normal run and in the .exe."""
from __future__ import annotations

import sys
from pathlib import Path


def resource_path(relative: str) -> Path:
    """The full path of a file inside the project (or inside the packaged program)."""
    base = getattr(sys, "_MEIPASS", None)        # set by PyInstaller
    root = Path(base) if base else Path(__file__).resolve().parent.parent
    return root / relative
