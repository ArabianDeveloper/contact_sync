"""Runs the core steps in order: clean, validate, remove duplicates."""
from __future__ import annotations

import logging

from app.config import DEFAULT_REGION
from app.core.cleaning import NameOptions
from app.core.dedupe import remove_duplicates
from app.core.models import Mapping, SourceTable, ValidationResult
from app.core.validation import validate_rows

logger = logging.getLogger("contact_sync.core.pipeline")


def process_table(
    table: SourceTable,
    mapping: Mapping,
    name_options: NameOptions = NameOptions(),
    region: str = DEFAULT_REGION,
) -> ValidationResult:
    """Validate every row first, then remove duplicates among the valid rows only."""
    result = validate_rows(table, mapping, name_options, region)
    kept, duplicates = remove_duplicates(result.valid_rows)
    result.valid_rows = kept
    result.duplicates = duplicates
    logger.info("Pipeline: valid=%d, duplicates removed=%d", result.valid_count, result.duplicate_count)
    return result
