"""Creates the Google API clients."""
from __future__ import annotations


def build_service(name: str, version: str, creds):
    """build_service('people', 'v1', creds), ('chat', 'v1', creds), ('sheets', 'v4', creds)."""
    from googleapiclient.discovery import build

    return build(name, version, credentials=creds, cache_discovery=False)
