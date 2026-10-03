"""Google Contacts: labels and contacts (People API).

Existing contacts are found by phone. All contacts are loaded once at the start of the
run and compared by normalized phone (E.164), which is more reliable than Google's search.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

from app.config import DEFAULT_REGION
from app.core.cleaning import parse_phone
from app.core.errors import ContactSyncError
from app.services.common import name_key, request_args
from app.services.errors import ALREADY_EXISTS, describe_error

logger = logging.getLogger("contact_sync.contacts")

ADDED = "added"
ALREADY = "already"


@dataclass
class ContactInfo:
    resource_name: str                                  # for example people/c123
    groups: set[str] = field(default_factory=set)       # label resource names the contact is in


@dataclass
class LabelRef:
    resource_name: str                                  # for example contactGroups/abc
    created: bool


class ContactsService:
    def __init__(self, people, region: str = DEFAULT_REGION):
        self._people = people
        self._region = region
        self._labels: dict[str, str] = {}               # name key -> label resource name
        self._contacts: dict[str, ContactInfo] = {}     # E.164 phone -> contact

    # ------------------------------------------------------------------ labels

    def load_labels(self) -> int:
        """Load the user's labels (system groups are ignored). Returns the count."""
        labels: dict[str, str] = {}
        token = None
        while True:
            response = self._people.contactGroups().list(**request_args(200, token)).execute()
            for group in response.get("contactGroups", []):
                if group.get("groupType") != "USER_CONTACT_GROUP":
                    continue
                name, resource = group.get("name"), group.get("resourceName")
                if name and resource:
                    labels.setdefault(name_key(name), resource)
            token = response.get("nextPageToken")
            if not token:
                break
        self._labels = labels
        logger.info("Labels loaded: %d", len(labels))
        return len(labels)

    def label_names_loaded(self) -> int:
        return len(self._labels)

    def ensure_label(self, name: str, create: bool = True) -> LabelRef | None:
        """Find the label. If it does not exist: create it when `create` is True, otherwise
        return None (the caller reports it)."""
        key = name_key(name)
        found = self._labels.get(key)
        if found:
            return LabelRef(found, False)
        if not create:
            return None

        try:
            group = self._people.contactGroups().create(
                body={"contactGroup": {"name": name.strip()}}
            ).execute()
        except Exception as exc:
            if describe_error(exc).kind == ALREADY_EXISTS:      # created meanwhile
                self.load_labels()
                found = self._labels.get(key)
                if found:
                    return LabelRef(found, False)
            raise

        resource = group.get("resourceName")
        if not resource:
            raise ContactSyncError("Google did not return the new label.")
        self._labels[key] = resource
        logger.info("Label created")
        return LabelRef(resource, True)

    def add_to_label(self, contact: ContactInfo, label_resource: str) -> str:
        """Add the contact to the label. Returns ADDED, or ALREADY if it was already in it."""
        if label_resource in contact.groups:
            return ALREADY
        response = self._people.contactGroups().members().modify(
            resourceName=label_resource,
            body={"resourceNamesToAdd": [contact.resource_name]},
        ).execute()
        if contact.resource_name in (response or {}).get("notFoundResourceNames", []):
            raise ContactSyncError("Google could not find the contact to add it to the label.")
        contact.groups.add(label_resource)
        return ADDED

    # ---------------------------------------------------------------- contacts

    def load_contacts(self, on_progress: Callable[[int], None] | None = None) -> int:
        """Load all contacts and index them by normalized phone. Returns the number of
        contacts read. If a phone is in several contacts, the first one is used."""
        index: dict[str, ContactInfo] = {}
        read = 0
        token = None
        while True:
            response = self._people.people().connections().list(
                **request_args(1000, token, resourceName="people/me", personFields="phoneNumbers,memberships")
            ).execute()
            for person in response.get("connections", []):
                read += 1
                resource = person.get("resourceName")
                if not resource:
                    continue
                groups = {
                    m["contactGroupMembership"]["contactGroupResourceName"]
                    for m in person.get("memberships", [])
                    if isinstance(m.get("contactGroupMembership"), dict)
                    and m["contactGroupMembership"].get("contactGroupResourceName")
                }
                info = ContactInfo(resource, groups)
                for number in person.get("phoneNumbers", []):
                    phone = parse_phone(number.get("value") or "", self._region)
                    if phone is None and number.get("canonicalForm"):
                        phone = parse_phone(number["canonicalForm"], self._region)
                    if phone is not None:
                        index.setdefault(phone, info)
            if on_progress:
                on_progress(read)
            token = response.get("nextPageToken")
            if not token:
                break
        self._contacts = index
        logger.info("Contacts loaded: %d contacts, %d phones", read, len(index))
        return read

    def find(self, phone: str) -> ContactInfo | None:
        """Find an existing contact by phone in E.164 format."""
        return self._contacts.get(phone)

    def create_contact(self, name: str, phone: str, email: str) -> ContactInfo:
        """Create a contact. The full name is stored as one value (no first/last split)."""
        body = {
            "names": [{"givenName": name}],
            "phoneNumbers": [{"value": phone}],
            "emailAddresses": [{"value": email}],
        }
        person = self._people.people().createContact(body=body).execute()
        resource = person.get("resourceName")
        if not resource:
            raise ContactSyncError("Google did not return the new contact.")
        info = ContactInfo(resource)
        self._contacts[phone] = info
        return info
