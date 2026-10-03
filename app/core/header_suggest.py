"""Auto-suggest the column mapping from the header names (English and Arabic)."""
from __future__ import annotations

import re

from app.core.models import Mapping

_ARABIC_MAP = str.maketrans({
    "\u0623": "\u0627", "\u0625": "\u0627", "\u0622": "\u0627", "\u0671": "\u0627",  # alef variants
    "\u0629": "\u0647",                                                             # teh marbuta
    "\u0649": "\u064a",                                                             # alef maksura
    "\u0624": "\u0648", "\u0626": "\u064a",
})
_DIACRITICS = re.compile("[\u064b-\u065f\u0670\u0640]")


def normalize_header(text: str) -> str:
    """Lowercase, unify Arabic letter variants, remove diacritics and punctuation."""
    text = text.casefold().translate(_ARABIC_MAP)
    text = _DIACRITICS.sub("", text)
    return re.sub(r"[\W_]+", " ", text).strip()


def _tokens(words: str) -> set[str]:
    return {normalize_header(word) for word in words.split()}


_EMAIL = _tokens("email emails mail البريد الايميل ايميل الاميل بريد")
_PHONE = _tokens("phone phones mobile mobiles tel telephone cell cellphone gsm هاتف الهاتف جوال الجوال موبايل الموبايل تلفون التلفون")
_LABELS = _tokens("label labels team teams group groups tag tags الفريق فريق الفرق المجموعة مجموعة المجموعات التصنيف تصنيف الوسوم")
_NAME = _tokens("name names surname fullname firstname lastname middlename familyname givenname first middle last family given اسم الاسم الاسماء اللقب لقب")

# Order matters: "Team Name" is a label column, "Email Name" is an email column.
_FIELDS = (("email", _EMAIL), ("phone", _PHONE), ("labels", _LABELS), ("name", _NAME))


def classify_header(header: str) -> str | None:
    tokens = set(normalize_header(header).split())
    for field_name, keywords in _FIELDS:
        if tokens & keywords:
            return field_name
    return None


def suggest_mapping(headers: list[str]) -> Mapping:
    """Suggest a mapping. Every name column found is suggested, in file order.
    If several columns match phone, email or labels, the first one is used."""
    mapping = Mapping()
    for index, header in enumerate(headers):
        field_name = classify_header(header)
        if field_name == "name":
            mapping.name_columns.append(index)
        elif field_name == "phone" and mapping.phone_column is None:
            mapping.phone_column = index
        elif field_name == "email" and mapping.email_column is None:
            mapping.email_column = index
        elif field_name == "labels" and mapping.labels_column is None:
            mapping.labels_column = index
    return mapping
