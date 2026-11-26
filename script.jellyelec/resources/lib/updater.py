"""Updating JellyELEC from its GitHub releases.

Each release on github.com/fattykidd/jellyelec has the add-on attached as
script.jellyelec-<version>.zip. Kodi's own add-on updates are off in JellyELEC images, so
JellyELEC checks for releases itself: once a day in the background, and whenever Check for
updates is chosen in Settings.

An update is unpacked into Kodi's own add-on folder (/storage/.kodi/addons), where Kodi
prefers it to the copy built into the image because its version is higher. Kodi is then
told to look again, and JellyELEC restarts into the new version.
"""

import io
import json
import os
import shutil
import time
import urllib.error
import urllib.request
import zipfile

import xbmc
import xbmcvfs

from resources.lib.kodi import ADDON_ID, ADDON_VERSION, PROFILE_PATH, log

GITHUB_REPOSITORY = "fattykidd/jellyelec"
LATEST_RELEASE_URL = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases/latest"
REQUEST_TIMEOUT_SECONDS = 20

ADDONS_FOLDER = "special://home/addons"
LAST_CHECK_FILE = os.path.join(PROFILE_PATH, "last_update_check")
CHECK_INTERVAL_SECONDS = 24 * 60 * 60


class UpdateError(Exception):
    """Checking for or installing an update didn't work."""


class Release:
    """A JellyELEC release on GitHub."""

    def __init__(self, version, zip_url, notes):
        self.version = version
        self.zip_url = zip_url
        self.notes = notes


def latest_release():
    """The newest release, or None if there's no release with an add-on zip yet."""
    data = _get_json(LATEST_RELEASE_URL)
    version = data.get("tag_name", "").lstrip("v")
    zip_name = f"{ADDON_ID}-{version}.zip"
    zip_url = next(
        (asset["browser_download_url"] for asset in data.get("assets", []) if asset.get("name") == zip_name),
        None,
    )
    if not version or not zip_url:
        return None
    return Release(version, zip_url, data.get("body") or "")


def available_update():
    """The latest release if it's newer than this version, else None. Raises UpdateError."""
    _remember_check()
    release = latest_release()
    if release and _version_key(release.version) > _version_key(ADDON_VERSION):
        log(f"Update available: {ADDON_VERSION} -> {release.version}.")
        return release
    return None


def check_is_due():
    """True if a day has passed since the last check (background checks only)."""
    try:
        return time.time() - os.path.getmtime(LAST_CHECK_FILE) >= CHECK_INTERVAL_SECONDS
    except OSError:
        return True


def install(release):
    """Download and unpack the release, and have Kodi pick it up. Raises UpdateError."""
    log(f"Installing JellyELEC {release.version}.")
    try:
        with urllib.request.urlopen(_request(release.zip_url), timeout=REQUEST_TIMEOUT_SECONDS) as response:
            archive = zipfile.ZipFile(io.BytesIO(response.read()))
    except (OSError, zipfile.BadZipFile) as error:
        raise UpdateError(f"Couldn't download the update: {error}") from error

    if f"{ADDON_ID}/addon.xml" not in archive.namelist():
        raise UpdateError("The downloaded file isn't a JellyELEC add-on.")

    addons_folder = xbmcvfs.translatePath(ADDONS_FOLDER)
    target = os.path.join(addons_folder, ADDON_ID)
    staging = os.path.join(addons_folder, f".{ADDON_ID}-update")
    shutil.rmtree(staging, ignore_errors=True)
    try:
        archive.extractall(staging)
        shutil.rmtree(target, ignore_errors=True)
        shutil.move(os.path.join(staging, ADDON_ID), target)
    except OSError as error:
        raise UpdateError(f"Couldn't install the update: {error}") from error
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    # Kodi looks through its add-on folders again and finds the newer version.
    xbmc.executebuiltin("UpdateLocalAddons", True)
    log(f"JellyELEC {release.version} installed.")


# Helpers ----------------------------------------------------------------------------

def _request(url):
    # GitHub's API turns away requests without a User-Agent.
    return urllib.request.Request(url, headers={"User-Agent": f"JellyELEC/{ADDON_VERSION}"})


def _get_json(url):
    try:
        with urllib.request.urlopen(_request(url), timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return {}  # no releases yet
        raise UpdateError(f"GitHub answered {error.code}.") from error
    except (OSError, ValueError) as error:
        raise UpdateError(f"Couldn't reach GitHub: {error}") from error


def _version_key(version):
    """'0.0.43' as (0, 0, 43), so versions compare as numbers, not text."""
    return tuple(int(part) for part in version.split(".") if part.isdigit())


def _remember_check():
    os.makedirs(PROFILE_PATH, exist_ok=True)
    with open(LAST_CHECK_FILE, "w", encoding="utf-8") as file:
        file.write(str(int(time.time())))
