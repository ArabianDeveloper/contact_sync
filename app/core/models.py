"""Data structures shared by the core modules."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator

from app.config import PREVIEW_ROWS


def column_letter(index: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA (spreadsheet style)."""
    letters = ""
    number = index + 1
    while number:
        number, remainder = divmod(number - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


@dataclass
class SourceTable:
    """All the cells of a file or sheet as text, exactly as read.

    Row numbers shown to the user are 1-based and are the row numbers of the
    original file or sheet.
    """

    rows: list[list[str]]
    file_type: str
    source_name: str = ""
    sheet_names: list[str] = field(default_factory=list)
    sheet_name: str | None = None
    encoding: str | None = None
    delimiter: str | None = None
    header_row: int = 0  # 0-based index into rows

    @property
    def column_count(self) -> int:
        return max((len(row) for row in self.rows), default=0)

    def set_header_row(self, index: int) -> None:
        if index < 0 or index >= len(self.rows):
            raise ValueError("Header row is outside the data.")
        self.header_row = index

    def _padded(self, row: list[str]) -> list[str]:
        width = self.column_count
        return row + [""] * (width - len(row))

    def headers(self) -> list[str]:
        """Header texts. An empty header is shown as 'Column A', 'Column B', ..."""
        row = self.rows[self.header_row] if self.header_row < len(self.rows) else []
        result = []
        for index in range(self.column_count):
            text = row[index].strip() if index < len(row) else ""
            result.append(text if text else f"Column {column_letter(index)}")
        return result

    def data_rows(self) -> Iterator[tuple[int, list[str]]]:
        """Yield (row number in the file, values) for the rows after the header.

        Rows where every cell is empty are skipped.
        """
        for index in range(self.header_row + 1, len(self.rows)):
            row = self._padded(self.rows[index])
            if any(cell.strip() for cell in row):
                yield index + 1, row

    def preview(self, count: int = PREVIEW_ROWS) -> list[tuple[int, list[str]]]:
        result = []
        for item in self.data_rows():
            result.append(item)
            if len(result) >= count:
                break
        return result


# ---------------------------------------------------------------------------
# Mapping, cleaned rows and validation results (stage 2)
# ---------------------------------------------------------------------------

@dataclass
class Mapping:
    """Which columns (0-based indexes) hold which field."""

    name_columns: list[int] = field(default_factory=list)  # joined in this order
    phone_column: int | None = None
    email_column: int | None = None
    labels_column: int | None = None

    def is_complete(self) -> bool:
        return bool(self.name_columns) and None not in (
            self.phone_column, self.email_column, self.labels_column
        )


@dataclass
class CleanRow:
    """A row that passed validation."""

    row_number: int
    name: str
    phone: str          # E.164, for example +96899123456
    email: str
    labels: list[str]


@dataclass
class RejectedRow:
    """A row that failed validation. The values are shown as read, for the report."""

    row_number: int
    name: str
    phone: str
    email: str
    labels: str
    reasons: list[str]


@dataclass
class DuplicateRow:
    """A row removed because its phone appears again later in the file."""

    row_number: int
    kept_row_number: int
    name: str
    phone: str
    labels: list[str]   # the merged labels of the kept row


@dataclass
class ValidationResult:
    total_rows: int
    valid_rows: list[CleanRow] = field(default_factory=list)
    rejected: list[RejectedRow] = field(default_factory=list)
    duplicates: list[DuplicateRow] = field(default_factory=list)

    @property
    def valid_count(self) -> int:
        return len(self.valid_rows)

    @property
    def rejected_count(self) -> int:
        return len(self.rejected)

    @property
    def duplicate_count(self) -> int:
        return len(self.duplicates)

    def distinct_labels(self) -> list[str]:
        """Labels of the valid rows, each once (ignoring upper/lower case), in file order."""
        seen: set[str] = set()
        result: list[str] = []
        for row in self.valid_rows:
            for label in row.labels:
                key = label.casefold()
                if key not in seen:
                    seen.add(key)
                    result.append(label)
        return result


# ---------------------------------------------------------------------------
# Import results (stage 5)
# ---------------------------------------------------------------------------

# Steps of one row
STEP_CONTACT = "contact"
STEP_LABEL = "label"
STEP_SPACE = "space"


@dataclass
class ItemResult:
    """A problem found while importing a row: a failure or something that was reported."""

    row_number: int
    name: str
    step: str                  # contact, label, space
    target: str | None         # the label or space name
    message: str               # readable reason
    error_kind: str | None = None


@dataclass
class RunSummary:
    total_rows: int = 0
    processed_rows: int = 0
    contacts_created: int = 0
    contacts_existing: int = 0
    added_to_labels: int = 0
    already_in_labels: int = 0
    added_to_spaces: int = 0
    already_in_spaces: int = 0
    labels_created: int = 0
    spaces_created: int = 0
    failed: list[ItemResult] = field(default_factory=list)
    reported: list[ItemResult] = field(default_factory=list)
    not_processed: list[int] = field(default_factory=list)   # row numbers
    cancelled: bool = False
    stopped_reason: str | None = None

    @property
    def failed_count(self) -> int:
        return len(self.failed)

    @property
    def stopped(self) -> bool:
        return self.stopped_reason is not None

    def reported_by_target(self) -> list[tuple[str, str, list[int]]]:
        """Reported items grouped as (step, label or space name, row numbers)."""
        groups: dict[tuple[str, str], list[int]] = {}
        for item in self.reported:
            groups.setdefault((item.step, item.target or ""), []).append(item.row_number)
        return [(step, target, rows) for (step, target), rows in groups.items()]
