"""Google Chat: spaces and members.

The Chat API lists only the spaces the signed-in user belongs to. A space that exists but
where the user is not a member is not found.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

from app.core.errors import ContactSyncError
from app.services.common import name_key, request_args
from app.services.errors import ALREADY_EXISTS, describe_error

logger = logging.getLogger("contact_sync.chat")

ADDED = "added"
ALREADY = "already"

_NOT_SPACES = {"GROUP_CHAT", "DIRECT_MESSAGE"}


class DuplicateSpaceError(ContactSyncError):
    """Several spaces have the label's name and no choice was made."""


@dataclass
class SpaceInfo:
    name: str                       # for example spaces/AAAA
    display_name: str
    create_time: str | None = None
    member_count: int | None = None


@dataclass
class SpaceRef:
    name: str
    display_name: str
    created: bool


class ChatService:
    def __init__(self, chat):
        self._chat = chat
        self._spaces: dict[str, list[SpaceInfo]] = {}     # name key -> spaces
        self._choices: dict[str, str | None] = {}         # name key -> chosen space (None = skip)

    # ------------------------------------------------------------------ spaces

    def load_spaces(self) -> int:
        """Load the spaces of the user. Returns the count."""
        spaces: dict[str, list[SpaceInfo]] = {}
        count = 0
        token = None
        while True:
            response = self._chat.spaces().list(**request_args(1000, token)).execute()
            for item in response.get("spaces", []):
                display = (item.get("displayName") or "").strip()
                name = item.get("name")
                if not display or not name or item.get("spaceType") in _NOT_SPACES:
                    continue
                members = item.get("membershipCount")
                member_count = members.get("joinedDirectHumanUserCount") if isinstance(members, dict) else None
                info = SpaceInfo(name, display, item.get("createTime"), member_count)
                spaces.setdefault(name_key(display), []).append(info)
                count += 1
            token = response.get("nextPageToken")
            if not token:
                break
        self._spaces = spaces
        logger.info("Spaces loaded: %d", count)
        return count

    def duplicate_names(self, labels: Iterable[str]) -> list[tuple[str, list[SpaceInfo]]]:
        """For the given labels, those that match more than one space, as (label, spaces).
        The user must choose one space for each (item 22)."""
        result, seen = [], set()
        for label in labels:
            key = name_key(label)
            if key in seen:
                continue
            seen.add(key)
            spaces = self._spaces.get(key, [])
            if len(spaces) > 1:
                result.append((label, list(spaces)))
        return result

    def unresolved_duplicates(self, labels: Iterable[str]) -> list[tuple[str, list[SpaceInfo]]]:
        """Like duplicate_names, but only the labels the user has not chosen a space for yet."""
        return [(label, spaces) for label, spaces in self.duplicate_names(labels)
                if name_key(label) not in self._choices]

    def was_skipped(self, label: str) -> bool:
        """True if the user chose to skip the space of this label."""
        key = name_key(label)
        return key in self._choices and self._choices[key] is None

    def choose(self, label: str, space_name: str | None) -> None:
        """Record the choice for a label with duplicate spaces. None means 'skip this space'."""
        key = name_key(label)
        if space_name is not None and space_name not in {s.name for s in self._spaces.get(key, [])}:
            raise ValueError("The chosen space is not one of the spaces with this name.")
        self._choices[key] = space_name

    def ensure_space(self, label: str, create: bool = True) -> SpaceRef | None:
        """Find the space of the label. If it does not exist: create it when `create` is True,
        otherwise return None (the caller reports it). Also returns None if the user chose to
        skip a label that has duplicate spaces."""
        key = name_key(label)
        found = self._spaces.get(key, [])

        if len(found) > 1:
            if key not in self._choices:
                raise DuplicateSpaceError(f"More than one space is named '{label.strip()}'. Choose one.")
            chosen = self._choices[key]
            if chosen is None:
                return None
            info = next(s for s in found if s.name == chosen)
            return SpaceRef(info.name, info.display_name, False)

        if found:
            return SpaceRef(found[0].name, found[0].display_name, False)
        if not create:
            return None

        display = label.strip()
        space = self._chat.spaces().create(body={"spaceType": "SPACE", "displayName": display}).execute()
        name = space.get("name")
        if not name:
            raise ContactSyncError("Google did not return the new space.")
        self._spaces.setdefault(key, []).append(SpaceInfo(name, display, space.get("createTime")))
        logger.info("Space created")
        return SpaceRef(name, display, True)

    # ----------------------------------------------------------------- members

    def add_member(self, space_name: str, email: str) -> str:
        """Add the person (by email) to the space. Returns ADDED, or ALREADY if already a member.
        Other errors are raised."""
        body = {"member": {"name": f"users/{email}", "type": "HUMAN"}}
        try:
            self._chat.spaces().members().create(parent=space_name, body=body).execute()
        except Exception as exc:
            if describe_error(exc).kind == ALREADY_EXISTS:
                return ALREADY
            raise
        return ADDED
