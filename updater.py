"""Checks GitHub for a newer release and installs it over the program files.

Your settings (config.json), logs and generated files are never touched. Before overwriting,
the current files are copied to backup/v<old version>/ so an update can be undone by hand.
"""
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from version import REPO, __version__

APP_DIR = Path(__file__).resolve().parent
LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"

# Never overwritten or created by an update
KEEP = {"config.json", "logs", "assets", "backup", ".git", "__pycache__", ".venv", "venv"}

# Downloads only come from GitHub
ALLOWED_HOSTS = {
    "api.github.com", "github.com", "codeload.github.com",
    "objects.githubusercontent.com", "release-assets.githubusercontent.com",
}

NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


class UpdateError(Exception):
    pass


@dataclass
class Release:
    version: str  # "1.2.0"
    tag: str  # "v1.2.0"
    notes: str  # release notes (Markdown)
    page_url: str
    download_url: str
    sha256: str  # empty if GitHub didn't provide a checksum


def parse_version(text: str) -> tuple[int, ...]:
    parts = []
    for piece in text.strip().lstrip("vV").split(".")[:3]:
        m = re.match(r"\d+", piece)
        parts.append(int(m.group()) if m else 0)
    return tuple(parts + [0] * (3 - len(parts)))


def _check_host(url: str) -> None:
    host = urlparse(url).hostname or ""
    if urlparse(url).scheme != "https" or host not in ALLOWED_HOSTS:
        raise UpdateError(f"Refusing to download from {host or url}")


def _get(url: str, timeout: float = 20) -> bytes:
    _check_host(url)
    req = Request(url, headers={
        "User-Agent": f"discord-uses-vm/{__version__}",
        "Accept": "application/vnd.github+json" if "api.github.com" in url else "*/*",
    })
    with urlopen(req, timeout=timeout) as resp:
        _check_host(resp.geturl())  # after redirects
        return resp.read()


def latest_release() -> Release | None:
    """The newest published release on GitHub, or None if there are none yet."""
    try:
        data = json.loads(_get(LATEST_URL))
    except HTTPError as e:
        if e.code == 404:
            return None
        raise UpdateError(f"GitHub answered {e.code} {e.reason}")
    except OSError as e:
        raise UpdateError(f"Couldn't reach GitHub: {e}")

    zips = [a for a in data.get("assets", []) if a.get("name", "").endswith(".zip")]
    if zips:
        asset = zips[0]
        url = asset["browser_download_url"]
        digest = asset.get("digest") or ""
        sha256 = digest.split(":", 1)[1] if digest.startswith("sha256:") else ""
    else:
        url, sha256 = data["zipball_url"], ""  # source code zip
    tag = data.get("tag_name", "")
    return Release(
        version=tag.lstrip("vV"), tag=tag, notes=data.get("body") or "",
        page_url=data.get("html_url", ""), download_url=url, sha256=sha256,
    )


def newer_release() -> Release | None:
    """The latest release if it's newer than the version running now."""
    release = latest_release()
    if release and parse_version(release.version) > parse_version(__version__):
        return release
    return None


def install(release: Release, app_dir: Path = APP_DIR) -> dict:
    """Download a release and copy its files over the program. Returns a short report."""
    try:
        data = _get(release.download_url, timeout=180)
    except OSError as e:
        raise UpdateError(f"Download failed: {e}")
    if release.sha256 and hashlib.sha256(data).hexdigest() != release.sha256.lower():
        raise UpdateError("The download is damaged (checksum doesn't match). Nothing was changed.")

    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise UpdateError("The download isn't a valid zip file. Nothing was changed.")
    names = [n for n in archive.namelist() if not n.endswith("/")]
    # GitHub's source zips put everything in one top folder; strip it
    tops = {n.split("/", 1)[0] for n in names}
    strip = next(iter(tops)) + "/" if len(tops) == 1 and all("/" in n for n in names) else ""
    files = {n[len(strip):]: n for n in names if n.startswith(strip)}
    if "gui.py" not in files or "version.py" not in files:
        raise UpdateError("The download doesn't look like this program. Nothing was changed.")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp).resolve()
        staged = []
        for rel_name, zip_name in files.items():
            if rel_name.split("/", 1)[0] in KEEP:
                continue
            target = (tmp_dir / rel_name).resolve()
            if tmp_dir not in target.parents:
                raise UpdateError(f"Unsafe path in the download: {rel_name}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(zip_name))
            staged.append(rel_name)

        old_requirements = _read(app_dir / "requirements.txt")
        backup_dir = app_dir / "backup" / f"v{__version__}"
        for rel_name in staged:
            current = app_dir / rel_name
            if current.is_file():
                (backup_dir / rel_name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(current, backup_dir / rel_name)
        for rel_name in staged:
            dest = app_dir / rel_name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(tmp_dir / rel_name, dest)

    report = {"files": len(staged), "backup": str(backup_dir), "deps": "unchanged"}
    if _read(app_dir / "requirements.txt") != old_requirements:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(app_dir / "requirements.txt")],
            capture_output=True, text=True, timeout=900, creationflags=NO_WINDOW,
        )
        if result.returncode == 0:
            report["deps"] = "updated"
        else:
            output = (result.stderr or result.stdout).strip().splitlines()
            report["deps"] = "failed: " + (output[-1] if output else "pip error")
    return report


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""
