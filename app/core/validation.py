"""Row validation. A row is valid only if name, phone, email and labels are present and valid."""
from __future__ import annotations

import logging

from app.config import DEFAULT_REGION
from app.core.cleaning import NameOptions, build_name, is_valid_email, parse_phone, split_labels
from app.core.models import CleanRow, Mapping, RejectedRow, SourceTable, ValidationResult

logger = logging.getLogger("contact_sync.core.validation")

MISSING_NAME = "Missing name"
MISSING_PHONE = "Missing phone"
INVALID_PHONE = "Invalid phone"
MISSING_EMAIL = "Missing email"
INVALID_EMAIL = "Invalid email"
MISSING_LABELS = "Missing labels"


def _cell(row: list[str], index: int | None) -> str:
    if index is None or index < 0 or index >= len(row):
        return ""
    return row[index]


def validate_row(
    row_number: int,
    row: list[str],
    mapping: Mapping,
    name_options: NameOptions = NameOptions(),
    region: str = DEFAULT_REGION,
) -> tuple[CleanRow | None, RejectedRow | None]:
    """Clean and validate one row. Returns (clean row, None) or (None, rejected row)."""
    reasons: list[str] = []

    name = build_name([_cell(row, i) for i in mapping.name_columns], name_options)
    if not name:
        reasons.append(MISSING_NAME)

    phone_raw = _cell(row, mapping.phone_column)
    phone = None
    if not phone_raw.strip():
        reasons.append(MISSING_PHONE)
    else:
        phone = parse_phone(phone_raw, region)
        if phone is None:
            reasons.append(INVALID_PHONE)

    email_raw = _cell(row, mapping.email_column)
    email = email_raw.strip()
    if not email:
        reasons.append(MISSING_EMAIL)
    elif not is_valid_email(email):
        reasons.append(INVALID_EMAIL)

    labels_raw = _cell(row, mapping.labels_column)
    labels = split_labels(labels_raw)
    if not labels:
        reasons.append(MISSING_LABELS)

    if reasons:
        return None, RejectedRow(
            row_number=row_number,
            name=name,
            phone=phone_raw.strip(),
            email=email,
            labels=labels_raw.strip(),
            reasons=reasons,
        )
    return CleanRow(row_number=row_number, name=name, phone=phone, email=email, labels=labels), None


def validate_rows(
    table: SourceTable,
    mapping: Mapping,
    name_options: NameOptions = NameOptions(),
    region: str = DEFAULT_REGION,
) -> ValidationResult:
    """Clean and validate every data row. Duplicate removal is a separate step."""
    if not mapping.is_complete():
        raise ValueError("The mapping is incomplete: name, phone, email and labels are required.")

    result = ValidationResult(total_rows=0)
    for row_number, row in table.data_rows():
        result.total_rows += 1
        clean, rejected = validate_row(row_number, row, mapping, name_options, region)
        if clean is not None:
            result.valid_rows.append(clean)
        else:
            result.rejected.append(rejected)

    logger.info(
        "Validation: total=%d, valid=%d, rejected=%d",
        result.total_rows, result.valid_count, result.rejected_count,
    )
    return result
