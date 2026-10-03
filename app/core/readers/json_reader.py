"""JSON reader. Supported shapes: a list of objects, or a list of lists."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.core.errors import ReadError
from app.core.models import SourceTable
from app.core.readers.cells import cell_to_text, trim_trailing_empty_rows
from app.core.readers.text_encoding import decode_text

logger = logging.getLogger("contact_sync.core.readers")

_SHAPE_MESSAGE = "Unsupported JSON structure. Expected a list of objects or a list of lists."


def _json_cell(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return cell_to_text(value)


def read_json(path: Path) -> SourceTable:
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise ReadError(f"The file could not be opened: {exc.strerror or exc}") from exc

    text, encoding = decode_text(data)
    try:
        content = json.loads(text.lstrip("\ufeff"))
    except ValueError as exc:
        raise ReadError(f"The file is not valid JSON: {exc}") from exc

    if not isinstance(content, list) or not content:
        raise ReadError(_SHAPE_MESSAGE)

    if all(isinstance(item, dict) for item in content):
        headers: list[str] = []
        for item in content:
            for key in item:
                if str(key) not in headers:
                    headers.append(str(key))
        rows = [headers]
        for item in content:
            lookup = {str(key): value for key, value in item.items()}
            rows.append([_json_cell(lookup.get(header)) for header in headers])
    elif all(isinstance(item, list) for item in content):
        rows = [[_json_cell(cell) for cell in item] for item in content]
    else:
        raise ReadError(_SHAPE_MESSAGE)

    rows = trim_trailing_empty_rows(rows)
    if not rows:
        raise ReadError("The file has no data.")

    logger.info("Read json file: encoding=%s, rows=%d", encoding, len(rows))
    return SourceTable(rows=rows, file_type="json", encoding=encoding)
