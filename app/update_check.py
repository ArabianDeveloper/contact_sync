"""Update check (item 51): is there a newer release in the GitHub repository?

One request to the latest release of a public repository. The program never downloads or
installs anything; it only tells the user and opens the release page in the browser.
Every failure (no internet, no release yet, a bad answer) returns None.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from packaging.version import InvalidVersion, Version

from app.config import GITHUB_REPO, VERSION

logger = logging.getLogger("contact_sync.update")

_REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_PAGE_PREFIX = "https://github.com/"


@dataclass
class UpdateInfo:
    version: str      # for example 1.2.0
    url: str          # the release page


def parse_version(tag: str) -> Version | None:
    """'v1.2.0' -> Version('1.2.0'); None if the tag is not a version."""
    try:
        return Version((tag or "").strip().lstrip("vV"))
    except InvalidVersion:
        return None


def check_for_update(
    repo: str | None = GITHUB_REPO,
    current: str = VERSION,
    timeout: float = 5.0,
    opener: Callable = urlopen,
) -> UpdateInfo | None:
    """Return the newer release, or None if there is none (or it could not be checked)."""
    if not repo or not _REPO_PATTERN.match(repo):
        logger.info("Update check skipped: no valid repository")
        return None

    request = Request(
        f"https://api.github.com/repos/{repo}/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "ContactSync-update-check"},
    )
    try:
        with opener(request, timeout=timeout) as response:
            data = json.load(response)
    except HTTPError as exc:
        logger.info("Update check: GitHub answered %s", exc.code)      # 404 = no release published yet
        return None
    except (URLError, OSError, ValueError) as exc:
        logger.info("Update check failed (%s)", type(exc).__name__)
        return None

    if not isinstance(data, dict):
        return None
    latest = parse_version(str(data.get("tag_name", "")))
    installed = parse_version(current)
    if latest is None or installed is None:
        logger.info("Update check: the version could not be read")
        return None
    if latest <= installed:
        logger.info("Update check: up to date")
        return None

    url = data.get("html_url")
    if not isinstance(url, str) or not url.startswith(_PAGE_PREFIX):
        url = f"{_PAGE_PREFIX}{repo}/releases/latest"       # never open an address from outside GitHub
    logger.info("Update check: version %s is available", latest)
    return UpdateInfo(str(latest), url)
