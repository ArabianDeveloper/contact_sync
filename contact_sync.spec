# -*- mode: python ; coding: utf-8 -*-
# PyInstaller settings for Contact Sync. Build with:  python build_exe.py
import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = os.path.abspath(SPECPATH)

# Files that must be inside the program folder
datas = [(os.path.join(ROOT, "assets", "icon.ico"), "assets")]
datas += collect_data_files("googleapiclient")      # the descriptions of the Google APIs (People, Chat, Sheets)
datas += collect_data_files("certifi")              # certificates for the secure connection to Google
datas += collect_data_files("httplib2")

# Modules that are loaded by name at run time. The phone metadata of every country is needed;
# the geography, carrier and time zone data of phonenumbers are not used by the program.
hiddenimports = collect_submodules(
    "phonenumbers",
    filter=lambda name: not any(skip in name for skip in ("geodata", "carrierdata", "tzdata")),
)
hiddenimports += ["python_calamine", "charset_normalizer", "email_validator"]

VERSION_FILE = os.path.join(ROOT, "installer", "version_info.txt")   # written by build_exe.py

a = Analysis(
    ["main.py"],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ContactSync",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,                                   # no black console window
    icon=os.path.join(ROOT, "assets", "icon.ico"),
    version=VERSION_FILE if os.path.exists(VERSION_FILE) else None,
)

# One-folder build: dist/ContactSync/ContactSync.exe (faster start, fewer antivirus warnings than one-file)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="ContactSync",
)
