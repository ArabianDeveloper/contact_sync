"""Builds the Windows program and its installer.

    pip install -r requirements-build.txt
    python build_exe.py                 PyInstaller, then the installer (if Inno Setup is installed)
    python build_exe.py --no-installer  only dist\\ContactSync\\ContactSync.exe

Results:
    dist\\ContactSync\\ContactSync.exe
    dist\\installer\\ContactSync-Setup-<version>.exe
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Mapping

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.config import APP_NAME, VERSION  # noqa: E402

VERSION_INFO = ROOT / "installer" / "version_info.txt"
EXE = ROOT / "dist" / "ContactSync" / "ContactSync.exe"
COMPANY = "ArabianDeveloper"


def version_tuple(version: str) -> tuple[int, int, int, int]:
    """'1.2.3' -> (1, 2, 3, 0)"""
    numbers = [int(n) for n in re.findall(r"\d+", version)[:4]]
    return tuple(numbers + [0] * (4 - len(numbers)))  # type: ignore[return-value]


def version_info_text(version: str = VERSION) -> str:
    """The version resource of the .exe (what Windows shows in the file properties)."""
    numbers = version_tuple(version)
    dotted = ".".join(str(n) for n in numbers)
    return f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={numbers},
    prodvers={numbers},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('040904B0', [
        StringStruct('CompanyName', '{COMPANY}'),
        StringStruct('FileDescription', '{APP_NAME}'),
        StringStruct('FileVersion', '{dotted}'),
        StringStruct('InternalName', 'ContactSync'),
        StringStruct('OriginalFilename', 'ContactSync.exe'),
        StringStruct('ProductName', '{APP_NAME}'),
        StringStruct('ProductVersion', '{dotted}')
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def find_iscc(
    environ: Mapping[str, str] = os.environ,
    exists: Callable[[str], bool] = os.path.exists,
    which: Callable[[str], str | None] = shutil.which,
) -> str | None:
    """The Inno Setup compiler (ISCC.exe), or None if it is not installed."""
    configured = environ.get("ISCC")
    if configured and exists(configured):
        return configured
    found = which("ISCC")
    if found:
        return found
    for variable in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        base = environ.get(variable)
        if not base:
            continue
        for folder in ("Inno Setup 6", os.path.join("Programs", "Inno Setup 6")):
            candidate = os.path.join(base, folder, "ISCC.exe")
            if exists(candidate):
                return candidate
    return None


def run(command: list[str]) -> None:
    print("\n> " + " ".join(command))
    subprocess.run(command, check=True, cwd=ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description=f"Build {APP_NAME} for Windows.")
    parser.add_argument("--no-installer", action="store_true", help="build only the program folder")
    args = parser.parse_args()

    if sys.platform != "win32":
        print("The Windows program must be built on Windows.")
        return 1
    if importlib.util.find_spec("PyInstaller") is None:
        print("PyInstaller is not installed. Run: pip install -r requirements-build.txt")
        return 1

    print(f"Building {APP_NAME} {VERSION}")
    VERSION_INFO.write_text(version_info_text(VERSION), encoding="utf-8")
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "contact_sync.spec"])
    if not EXE.is_file():
        print(f"The build did not create {EXE}")
        return 1
    print(f"\nProgram folder: {EXE.parent}")

    if args.no_installer:
        return 0
    iscc = find_iscc()
    if iscc is None:
        print("\nInno Setup was not found, so the installer was not built.")
        print("Install Inno Setup 6.3 or newer from https://jrsoftware.org/isinfo.php and run this again,")
        print("or set the ISCC environment variable to the path of ISCC.exe.")
        return 0
    run([iscc, f"/DAppVersion={VERSION}", str(ROOT / "installer" / "contact_sync.iss")])
    print(f"\nInstaller: {ROOT / 'dist' / 'installer' / f'ContactSync-Setup-{VERSION}.exe'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
