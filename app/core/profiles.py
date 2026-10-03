"""Saved mapping profiles (item 7).

A profile is found by the set of header names of the file (trimmed, lowercase), so the
same layout is recognized even if the columns are in a different order. It stores the
header names, not column numbers, and is applied only if every stored header exists
exactly once in the loaded file.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path

from app import paths
from app.core.models import Mapping

logger = logging.getLogger("contact_sync.profiles")

_VERSION = 1


def _norm(header: str) -> str:
    return header.strip().casefold()


def profile_key(headers: list[str]) -> str:
    joined = "\x1f".join(sorted(_norm(h) for h in headers))
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()


def mapping_to_profile(mapping: Mapping, headers: list[str]) -> dict:
    def name_of(index: int | None) -> str | None:
        return headers[index] if index is not None and 0 <= index < len(headers) else None

    return {
        "name": [headers[i] for i in mapping.name_columns if 0 <= i < len(headers)],
        "phone": name_of(mapping.phone_column),
        "email": name_of(mapping.email_column),
        "labels": name_of(mapping.labels_column),
    }


def profile_to_mapping(profile: dict, headers: list[str]) -> Mapping | None:
    """Build a mapping from a profile, or None if a header is missing or appears twice."""
    positions: dict[str, list[int]] = {}
    for index, header in enumerate(headers):
        positions.setdefault(_norm(header), []).append(index)

    def find(header: object) -> int | None:
        if not isinstance(header, str):
            return None
        found = positions.get(_norm(header), [])
        return found[0] if len(found) == 1 else None

    name_headers = profile.get("name")
    if not isinstance(name_headers, list) or not name_headers:
        return None
    name_columns = [find(h) for h in name_headers]
    phone, email, labels = find(profile.get("phone")), find(profile.get("email")), find(profile.get("labels"))
    if None in name_columns or None in (phone, email, labels):
        return None
    return Mapping(name_columns=name_columns, phone_column=phone, email_column=email, labels_column=labels)


def _load_all(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("Profiles file could not be read (%s)", type(exc).__name__)
        return {}
    profiles = data.get("profiles") if isinstance(data, dict) else None
    return profiles if isinstance(profiles, dict) else {}


def find_profile(headers: list[str], path: Path | None = None) -> Mapping | None:
    path = Path(path) if path else paths.profiles_path()
    profile = _load_all(path).get(profile_key(headers))
    if not isinstance(profile, dict):
        return None
    return profile_to_mapping(profile, headers)


def save_profile(headers: list[str], mapping: Mapping, path: Path | None = None) -> None:
    path = Path(path) if path else paths.profiles_path()
    profiles = _load_all(path)
    profiles[profile_key(headers)] = mapping_to_profile(mapping, headers)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(
        json.dumps({"version": _VERSION, "profiles": profiles}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temp, path)
