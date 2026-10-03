"""Detects the type of a data file from its content (the extension is not trusted)."""
from __future__ import annotations

import json
import logging
import zipfile
from pathlib import Path

from app.core.errors import ReadError, UnsupportedFileError
from app.core.readers.csv_reader import detect_delimiter
from app.core.readers.text_encoding import decode_text

logger = logging.getLogger("contact_sync.core.readers")

_ZIP_SIGNATURE = b"PK\x03\x04"
_OLE_SIGNATURE = bytes.fromhex("D0CF11E0A1B11AE1")
_ODS_MIMETYPE = "application/vnd.oasis.opendocument.spreadsheet"

SUPPORTED_TYPES = ("xlsx", "xls", "ods", "csv", "tsv", "json")


def detect_file_type(path: Path) -> str:
    """Return one of: xlsx, xls, ods, csv, tsv, json."""
    path = Path(path)
    if not path.is_file():
        raise UnsupportedFileError(f"The file was not found: {path}")

    try:
        with open(path, "rb") as handle:
            head = handle.read(8)
    except OSError as exc:
        raise ReadError(f"The file could not be opened: {exc.strerror or exc}") from exc

    if not head:
        raise ReadError("The file is empty.")

    if head.startswith(_ZIP_SIGNATURE):
        file_type = _detect_zip(path)
    elif head.startswith(_OLE_SIGNATURE):
        file_type = "xls"
    else:
        file_type = _detect_text(path)

    logger.info("Detected file type: %s", file_type)
    return file_type


def _detect_zip(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            if "mimetype" in names:
                mimetype = archive.read("mimetype").decode("ascii", "ignore").strip()
                if mimetype == _ODS_MIMETYPE:
                    return "ods"
            if "xl/workbook.xml" in names:
                return "xlsx"
    except zipfile.BadZipFile as exc:
        raise UnsupportedFileError("The file is damaged or is not a supported file.") from exc
    raise UnsupportedFileError(
        "The file is an archive but not a spreadsheet. Supported types: "
        "XLSX, XLS, ODS, CSV, TSV, JSON."
    )


def _detect_text(path: Path) -> str:
    data = path.read_bytes()
    text, encoding = decode_text(data)

    if encoding != "utf-16" and b"\x00" in data[:4096]:
        raise UnsupportedFileError(
            "The file is not a supported file. Supported types: XLSX, XLS, ODS, CSV, TSV, JSON."
        )

    stripped = text.lstrip("\ufeff \t\r\n")
    if stripped[:1] in ("[", "{"):
        try:
            json.loads(stripped)
            return "json"
        except ValueError:
            pass  # not JSON, treat as delimited text

    return "tsv" if detect_delimiter(text) == "\t" else "csv"
