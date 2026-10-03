"""The state of the window and the rules between the steps. No Qt code, so it can be tested.

The pages read and change this object; they never keep their own copy of the data.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from pathlib import Path

from app.config import DEFAULT_REGION
from app.core.cleaning import NameOptions
from app.core.header_suggest import suggest_mapping
from app.core.models import Mapping, RunSummary, SourceTable, ValidationResult
from app.core.profiles import find_profile, save_profile
from app.core.validation import validate_row
from app.settings import Settings, load_settings, save_settings

logger = logging.getLogger("contact_sync.ui.state")

# Steps (the order of the pages in the window)
SOURCE, MAPPING, VALIDATION, IMPORT, RESULTS, SETTINGS = range(6)
STEP_TITLES = ["Source", "Mapping", "Validation", "Import", "Results", "Settings"]


@dataclass
class SampleRow:
    row_number: int
    name: str
    phone: str
    email: str
    labels: str
    problems: str          # empty when the row is valid


class AppState:
    def __init__(self, settings_path: Path | None = None, profiles_path: Path | None = None):
        self._settings_path = settings_path
        self._profiles_path = profiles_path
        self.settings: Settings = load_settings(settings_path)

        self.source_kind = "file"           # "file" or "gsheet"
        self.path: Path | None = None
        self.source_text = ""               # Google Sheet link or ID
        self.cell_range = ""                # Google Sheet range ("" = the whole tab)
        self.table: SourceTable | None = None
        self.mapping = Mapping()
        self.mapping_ready = False          # a mapping was prepared for the current table/header row
        self.mapping_from_profile = False
        self.result: ValidationResult | None = None
        self.summary: RunSummary | None = None
        self.running = False                # an import is running

    # ------------------------------------------------------------------ source

    def set_table(self, path: str | Path, table: SourceTable) -> None:
        """A file was read. Everything that depends on the previous data is cleared."""
        self.source_kind = "file"
        self.path = Path(path)
        self.source_text = ""
        self.cell_range = ""
        self.table = table
        self._reset_after_source()

    def set_google_table(self, text: str, table: SourceTable, cell_range: str = "") -> None:
        """A Google Sheet was read."""
        self.source_kind = "gsheet"
        self.path = None
        self.source_text = text.strip()
        self.cell_range = cell_range.strip()
        self.table = table
        self._reset_after_source()

    def reset_all(self) -> None:
        """Start a new import (the settings are kept)."""
        self.source_kind = "file"
        self.path = None
        self.source_text = ""
        self.cell_range = ""
        self.table = None
        self.running = False
        self._reset_after_source()

    def set_header_row(self, index: int) -> None:
        if self.table is None:
            return
        self.table.set_header_row(index)
        self._reset_after_source()

    def _reset_after_source(self) -> None:
        self.mapping = Mapping()
        self.mapping_ready = False
        self.mapping_from_profile = False
        self.result = None
        self.summary = None

    def headers(self) -> list[str]:
        return self.table.headers() if self.table else []

    # ----------------------------------------------------------------- mapping

    def ensure_mapping(self) -> None:
        """Prepare the mapping once per table and header row: a saved profile if there is one,
        otherwise the suggestion from the header names."""
        if self.mapping_ready or self.table is None:
            return
        headers = self.headers()
        profile = find_profile(headers, self._profiles_path)
        if profile is not None:
            self.mapping, self.mapping_from_profile = profile, True
        else:
            self.mapping, self.mapping_from_profile = suggest_mapping(headers), False
        self.mapping_ready = True

    def invalidate_result(self) -> None:
        """The mapping or a cleaning option changed: the validation must be done again."""
        self.result = None
        self.summary = None

    def name_options(self) -> NameOptions:
        return NameOptions.from_settings(self.settings)

    def save_current_profile(self) -> None:
        if self.table is not None and self.mapping.is_complete():
            save_profile(self.headers(), self.mapping, self._profiles_path)

    def sample_preview(self, count: int = 5, region: str = DEFAULT_REGION) -> list[SampleRow]:
        """The first rows as they would be imported, to check the mapping."""
        if self.table is None or not self.mapping.is_complete():
            return []
        options = self.name_options()
        rows = []
        for row_number, row in self.table.data_rows():
            clean, rejected = validate_row(row_number, row, self.mapping, options, region)
            if clean is not None:
                rows.append(SampleRow(row_number, clean.name, clean.phone, clean.email,
                                      ", ".join(clean.labels), ""))
            else:
                rows.append(SampleRow(row_number, rejected.name, rejected.phone, rejected.email,
                                      rejected.labels, "; ".join(rejected.reasons)))
            if len(rows) >= count:
                break
        return rows

    # -------------------------------------------------------------- validation

    def set_result(self, result: ValidationResult) -> None:
        self.result = result
        self.summary = None

    # ---------------------------------------------------------------- settings

    def update_settings(self, **changes) -> None:
        """Change settings and save them to the user data file."""
        self.settings = replace(self.settings, **changes)
        save_settings(self.settings, self._settings_path)

    # ------------------------------------------------------------------ import

    def import_overview(self) -> list[tuple[str, str]]:
        """Caption and value pairs shown before the import starts (counts from the validation)."""
        result = self.result
        if result is None:
            return []
        on_off = lambda value: "On" if value else "Off"
        return [
            ("Rows read", str(result.total_rows)),
            ("Rows to import", str(result.valid_count)),
            ("Rejected rows (not imported)", str(result.rejected_count)),
            ("Duplicate rows removed", str(result.duplicate_count)),
            ("Distinct labels", str(len(result.distinct_labels()))),
            ("Create missing labels", on_off(self.settings.auto_create_labels)),
            ("Create missing spaces", on_off(self.settings.auto_create_spaces)),
        ]

    def finish_run(self, summary: RunSummary) -> None:
        self.running = False
        self.summary = summary

    # -------------------------------------------------------------- navigation

    def can_open(self, step: int) -> bool:
        if self.running:
            return step == IMPORT        # nothing else can be opened while an import runs
        if step in (SOURCE, SETTINGS):
            return True
        if step == MAPPING:
            return self.table is not None
        if step == VALIDATION:
            return self.result is not None
        if step == IMPORT:
            return self.result is not None and self.result.valid_count > 0
        if step == RESULTS:
            return self.summary is not None
        return False
