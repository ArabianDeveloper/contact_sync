"""Cleaning of phone, name, email and labels."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from app.config import DEFAULT_REGION
from app.core.errors import MissingLibraryError

# --------------------------------------------------------------------------
# Characters
# --------------------------------------------------------------------------

_ARABIC_RANGES = (
    (0x0600, 0x06FF),
    (0x0750, 0x077F),
    (0x08A0, 0x08FF),
    (0xFB50, 0xFDFF),
    (0xFE70, 0xFEFF),
)

# Arabic-Indic (U+0660..U+0669) and Eastern Arabic-Indic (U+06F0..U+06F9) digits
_DIGIT_TABLE = {0x0660 + i: ord("0") + i for i in range(10)}
_DIGIT_TABLE.update({0x06F0 + i: ord("0") + i for i in range(10)})

_SPACE_LIKE = {"\u00a0", "\u2007", "\u202f", "\u2009", "\u200a", "\u2002", "\u2003", "\u3000"}
_PHONE_SEPARATORS = set(" -.()\u2010\u2011\u2012\u2013\u2014\u2212")
_PHONE_PATTERN = re.compile(r"^\+?\d+$")


def contains_arabic(text: str) -> bool:
    for ch in text:
        code = ord(ch)
        for start, end in _ARABIC_RANGES:
            if start <= code <= end:
                return True
    return False


def normalize_digits(text: str) -> str:
    """Convert Arabic-Indic digits to Latin digits."""
    return text.translate(_DIGIT_TABLE)


def remove_hidden_characters(text: str) -> str:
    """Remove direction marks, zero-width characters and the BOM; non-breaking spaces become spaces."""
    result = []
    for ch in text:
        if ch in _SPACE_LIKE:
            result.append(" ")
            continue
        category = unicodedata.category(ch)
        if category == "Cf":
            continue
        if category == "Cc":
            if ch in "\t\r\n":
                result.append(" ")
            continue
        result.append(ch)
    return "".join(result)


# --------------------------------------------------------------------------
# Phone
# --------------------------------------------------------------------------

def clean_phone_text(text: str) -> str:
    """Prepare a phone text for parsing.

    Latin digits, hidden characters removed, separators (space, dash, dot, brackets)
    removed, a leading 00 turned into +. If other characters remain (letters, for
    example "ext"), they are kept so the number is rejected later.
    """
    text = remove_hidden_characters(normalize_digits(text)).strip()
    text = "".join(ch for ch in text if ch not in _PHONE_SEPARATORS)
    if text.startswith("00"):
        text = "+" + text[2:]
    return text


def parse_phone(text: str, region: str = DEFAULT_REGION) -> str | None:
    """Return the phone in E.164 format (for example +96899123456), or None if it is not valid."""
    cleaned = clean_phone_text(text)
    if not cleaned or not _PHONE_PATTERN.match(cleaned):
        return None

    try:
        import phonenumbers
    except ImportError as exc:
        raise MissingLibraryError("The library 'phonenumbers' is not installed.") from exc

    try:
        number = phonenumbers.parse(cleaned, region)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(number):
        return None
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)


# --------------------------------------------------------------------------
# Name
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class NameOptions:
    trim: bool = True
    collapse_spaces: bool = True
    capitalize: bool = True

    @classmethod
    def from_settings(cls, settings) -> "NameOptions":
        return cls(settings.name_trim, settings.name_collapse_spaces, settings.name_capitalize)


_WORD = re.compile(r"\S+")
_SEGMENT = re.compile(r"[^\-'\u2019]+")


def _capitalize_word(word: str) -> str:
    letters = "".join(ch for ch in word if ch.isalpha())
    if not letters:
        return word
    if not (letters.islower() or letters.isupper()):
        return word  # mixed case (for example McDonald) is kept
    return _SEGMENT.sub(lambda m: m.group(0)[:1].upper() + m.group(0)[1:].lower(), word)


def capitalize_words(text: str) -> str:
    return _WORD.sub(lambda m: _capitalize_word(m.group(0)), text)


def build_name(parts: list[str], options: NameOptions = NameOptions()) -> str:
    """Join the name columns with one space and clean the result.

    Empty parts are skipped. A name that contains an Arabic character is left
    untouched. Returns an empty string if every part is empty.
    """
    used = [part for part in parts if part and part.strip()]
    if not used:
        return ""
    name = " ".join(used)
    if contains_arabic(name):
        return name
    if options.trim:
        name = name.strip()
    if options.collapse_spaces:
        name = re.sub(r"\s+", " ", name)
    if options.capitalize:
        name = capitalize_words(name)
    return name


# --------------------------------------------------------------------------
# Email
# --------------------------------------------------------------------------

def is_valid_email(text: str) -> bool:
    """Format check only (no internet check)."""
    text = text.strip()
    if not text:
        return False

    try:
        from email_validator import EmailNotValidError, validate_email
    except ImportError as exc:
        raise MissingLibraryError("The library 'email-validator' is not installed.") from exc

    try:
        validate_email(text, check_deliverability=False)
    except EmailNotValidError:
        return False
    return True


# --------------------------------------------------------------------------
# Labels
# --------------------------------------------------------------------------

def split_labels(text: str, separator: str = ",") -> list[str]:
    """Split by the separator, trim each item, drop empty items and repeated items."""
    labels: list[str] = []
    seen: set[str] = set()
    for item in text.split(separator):
        label = item.strip()
        if not label:
            continue
        key = label.casefold()
        if key in seen:
            continue
        seen.add(key)
        labels.append(label)
    return labels
