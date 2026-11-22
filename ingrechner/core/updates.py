"""Prüfung auf neue Versionen über die GitHub-Releases des Projekts.

Es wird nur eine einfache Anfrage an die öffentliche GitHub-API gesendet
(keine Nutzer- oder Projektdaten). Die Prüfung lässt sich in den Einstellungen
abschalten; ohne Internet schlägt sie still fehl.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from .. import APP_NAME, UPDATE_REPO, __version__

API_URL = f"https://api.github.com/repos/{UPDATE_REPO}/releases/latest"


@dataclass
class ReleaseInfo:
    version: str
    url: str                    # Release-Seite
    installer_url: str | None   # direkter Download des Setups, falls vorhanden
    notes: str = ""


def parse_version(text: str) -> tuple[int, ...]:
    """„v1.2.3“ → (1, 2, 3); Zusätze wie „-beta“ werden ignoriert."""
    m = re.match(r"^\s*v?(\d+(?:\.\d+)*)", text or "")
    if not m:
        raise ValueError(f"Keine gültige Versionsnummer: {text!r}")
    parts = [int(p) for p in m.group(1).split(".")]
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def is_newer(candidate: str, current: str = __version__) -> bool:
    try:
        return parse_version(candidate) > parse_version(current)
    except ValueError:
        return False


def parse_release(data: dict) -> ReleaseInfo:
    tag = str(data.get("tag_name", ""))
    installer = next((a.get("browser_download_url") for a in data.get("assets", [])
                      if str(a.get("name", "")).lower().endswith(".exe")), None)
    return ReleaseInfo(version=tag.lstrip("vV"), url=str(data.get("html_url", "")), installer_url=installer,
                       notes=str(data.get("body") or ""))


def fetch_latest(timeout: float = 6.0, opener=urllib.request.urlopen) -> ReleaseInfo | None:
    """Neuestes Release oder ``None`` (noch kein Release veröffentlicht)."""
    req = urllib.request.Request(API_URL, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{APP_NAME.replace(' ', '-')}/{__version__}",
    })
    try:
        with opener(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:      # noch kein Release
            return None
        raise
    return parse_release(data)
