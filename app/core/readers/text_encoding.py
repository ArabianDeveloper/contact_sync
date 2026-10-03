"""Encoding detection for text files (CSV, TSV, JSON)."""
from __future__ import annotations

import codecs
import logging

from charset_normalizer import from_bytes

logger = logging.getLogger("contact_sync.core.readers")

_SAMPLE_SIZE = 2_000_000


def detect_encoding(data: bytes) -> str:
    """Return a Python codec name for the bytes.

    Order: UTF-8 with BOM, UTF-16 with BOM, UTF-8, then the detector, then
    Windows-1256 (Arabic) as the last choice.
    """
    if data.startswith(codecs.BOM_UTF8):
        return "utf-8-sig"
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return "utf-16"
    try:
        data.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass

    best = from_bytes(data[:_SAMPLE_SIZE]).best()
    if best is not None and best.encoding:
        return best.encoding
    return "cp1256"


def decode_text(data: bytes) -> tuple[str, str]:
    """Return (text, encoding)."""
    encoding = detect_encoding(data)
    try:
        text = data.decode(encoding)
    except (UnicodeDecodeError, LookupError):
        logger.warning("Decoding with %s failed, replacement characters are used", encoding)
        text = data.decode(encoding if _is_known(encoding) else "cp1256", errors="replace")
    return text, encoding


def _is_known(encoding: str) -> bool:
    try:
        codecs.lookup(encoding)
        return True
    except LookupError:
        return False
