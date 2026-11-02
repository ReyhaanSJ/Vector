"""Updates: VECTOR versions are GitHub Releases (v0.2.0, v0.3.0, ...).

    vector --versions          list every version
    vector --update            install the newest version
    vector --update 0.2.0      install a specific version (also to go back)

The app also checks once a day and offers the update from its tray icon.
While the GitHub repo is private, set VECTOR_GITHUB_TOKEN to a GitHub token that can read it.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

from vector import __version__
from vector.config import HOME_DIR

REPO = "ReyhaanSJ/Vector"
API = f"https://api.github.com/repos/{REPO}"
CHECK_FILE = HOME_DIR / "update-check.json"
CHECK_EVERY = 24 * 3600


class UpdateError(RuntimeError):
    pass


@dataclass
class Release:
    tag: str
    name: str
    notes: str
    published: str
    prerelease: bool = False

    @property
    def version(self) -> str:
        return self.tag.lstrip("vV")


def parse_version(text: str) -> tuple[int, ...]:
    """'v0.10.2' -> (0, 10, 2). Anything after the numbers (like '-beta') is ignored."""
    match = re.match(r"v?(\d+(?:\.\d+)*)", text.strip(), re.IGNORECASE)
    if not match:
        raise UpdateError(f"'{text}' isn't a version number")
    return tuple(int(p) for p in match.group(1).split("."))


def _padded(a: tuple[int, ...], b: tuple[int, ...]):
    width = max(len(a), len(b))
    return a + (0,) * (width - len(a)), b + (0,) * (width - len(b))


def is_newer(candidate: str, current: str = __version__) -> bool:
    a, b = _padded(parse_version(candidate), parse_version(current))
    return a > b


def same_version(a: str, b: str) -> bool:
    x, y = _padded(parse_version(a), parse_version(b))
    return x == y


def _request(url: str, accept: str = "application/vnd.github+json"):
    headers = {"Accept": accept, "User-Agent": f"VECTOR/{__version__}"}
    token = os.environ.get("VECTOR_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise UpdateError(
                "Couldn't find VECTOR's releases. If the GitHub repo is private, set "
                "VECTOR_GITHUB_TOKEN to a token that can read it.") from exc
        if exc.code == 403:
            raise UpdateError("GitHub is rate-limiting update checks. Try again in an hour.") from exc
        raise UpdateError(f"GitHub error {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise UpdateError("Couldn't reach GitHub. Check your internet connection.") from exc


def list_releases(include_prereleases: bool = False) -> list[Release]:
    with _request(f"{API}/releases?per_page=50") as resp:
        data = json.loads(resp.read())
    releases = [
        Release(tag=r["tag_name"], name=r.get("name") or r["tag_name"], notes=r.get("body") or "",
                published=(r.get("published_at") or "")[:10], prerelease=bool(r.get("prerelease")))
        for r in data if not r.get("draft")
    ]
    if not include_prereleases:
        releases = [r for r in releases if not r.prerelease]
    return sorted(releases, key=lambda r: parse_version(r.tag), reverse=True)


def latest_release() -> Release | None:
    releases = list_releases()
    return releases[0] if releases else None


def find_release(version: str) -> Release:
    for r in list_releases(include_prereleases=True):
        if same_version(r.tag, version):
            return r
    raise UpdateError(f"There is no VECTOR version {version}. See: vector --versions")


def check_for_update(force: bool = False) -> Release | None:
    """The newest release if it's newer than this one. Checks GitHub at most once a day."""
    now = time.time()
    if not force:
        try:
            cached = json.loads(CHECK_FILE.read_text(encoding="utf-8"))
            if now - cached.get("checked", 0) < CHECK_EVERY:
                tag = cached.get("latest")
                if tag and is_newer(tag):
                    return Release(tag=tag, name=tag, notes=cached.get("notes", ""), published="")
                return None
        except (OSError, ValueError):
            pass
    latest = latest_release()
    try:
        CHECK_FILE.parent.mkdir(parents=True, exist_ok=True)
        CHECK_FILE.write_text(json.dumps({
            "checked": now, "latest": latest.tag if latest else None,
            "notes": latest.notes[:2000] if latest else ""}), encoding="utf-8")
    except OSError:
        pass
    return latest if latest and is_newer(latest.tag) else None


def download_release(release: Release, dest: Path) -> Path:
    """Download and unpack a release; returns the folder holding install.ps1."""
    dest.mkdir(parents=True, exist_ok=True)
    zip_path = dest / f"vector-{release.version}.zip"
    with _request(f"{API}/zipball/{release.tag}") as resp:  # GitHub redirects to the ZIP
        zip_path.write_bytes(resp.read())
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.namelist():
            target = (dest / member).resolve()
            if not str(target).startswith(str(dest.resolve())):
                raise UpdateError("The download looks damaged (unsafe file paths).")
        archive.extractall(dest)
    installers = sorted(dest.glob("*/install.ps1"))
    if not installers:
        raise UpdateError("That version can't update itself (it has no install.ps1).")
    return installers[0].parent


def install_release(release: Release) -> None:
    """Hand over to that version's installer, which closes VECTOR, updates it and reopens it.
    Your settings, memory and AI choice are kept."""
    if sys.platform != "win32":
        raise UpdateError("Automatic updates are Windows-only for now. Use: git pull && pip install -e .")
    folder = download_release(release, Path(tempfile.mkdtemp(prefix="vector-update-")))
    env = dict(os.environ, VECTOR_INSTALL_YES="1", VECTOR_INSTALL_KEEP_SETTINGS="1",
               VECTOR_INSTALL_LAUNCH="1")
    subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", str(folder / "install.ps1")],
        cwd=str(folder), env=env, creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
