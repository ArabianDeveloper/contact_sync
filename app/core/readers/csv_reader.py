"""CSV and TSV reader with delimiter detection."""
from __future__ import annotations

import csv
import io
import logging
from collections import Counter
from pathlib import Path

from app.core.errors import ReadError
from app.core.models import SourceTable
from app.core.readers.cells import trim_trailing_empty_rows
from app.core.readers.text_encoding import decode_text

logger = logging.getLogger("contact_sync.core.readers")

CANDIDATE_DELIMITERS = [",", ";", "\t", "|"]

csv.field_size_limit(10_000_000)


def detect_delimiter(text: str) -> str:
    """Choose the delimiter that splits the first lines into the most consistent columns."""
    lines = [line for line in text.splitlines() if line.strip()][:30]
    if not lines:
        return ","

    best = ","
    best_score = (0.0, 0)
    for delimiter in CANDIDATE_DELIMITERS:
        try:
            rows = list(csv.reader(lines, delimiter=delimiter))
        except csv.Error:
            continue
        counts = [len(row) for row in rows if row]
        if not counts:
            continue
        mode, frequency = Counter(counts).most_common(1)[0]
        if mode < 2:
            continue
        score = (frequency / len(counts), mode)
        if score > best_score:
            best, best_score = delimiter, score
    return best


def read_csv(path: Path) -> SourceTable:
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise ReadError(f"The file could not be opened: {exc.strerror or exc}") from exc
    if not data.strip():
        raise ReadError("The file is empty.")

    text, encoding = decode_text(data)
    if text.startswith("\ufeff"):
        text = text[1:]
    delimiter = detect_delimiter(text)

    try:
        rows = [list(row) for row in csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)]
    except csv.Error as exc:
        raise ReadError(f"The file is not a valid CSV file: {exc}") from exc

    rows = trim_trailing_empty_rows(rows)
    if not rows:
        raise ReadError("The file has no data.")

    file_type = "tsv" if delimiter == "\t" else "csv"
    logger.info("Read %s file: encoding=%s, rows=%d", file_type, encoding, len(rows))
    return SourceTable(rows=rows, file_type=file_type, encoding=encoding, delimiter=delimiter)
