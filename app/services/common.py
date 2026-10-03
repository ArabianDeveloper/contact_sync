"""Helpers shared by the Google services."""
from __future__ import annotations


def name_key(name: str) -> str:
    """Key used to match label and space names: trimmed, ignoring upper/lower case."""
    return name.strip().casefold()


def request_args(page_size: int, page_token: str | None, **extra) -> dict:
    """Arguments of a list request. The page token is added only when there is one."""
    args = {"pageSize": page_size, **extra}
    if page_token:
        args["pageToken"] = page_token
    return args
