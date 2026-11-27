"""Updating JellyELEC from its GitHub releases.

github.com/fattykidd/jellyelec has two kinds of release:

- Add-on releases, tagged v0.0.59 and so on, with the add-on attached as
  script.jellyelec-<version>.zip. An add-on update is unpacked into Kodi's own add-on folder
  (/storage/.kodi/addons), where Kodi prefers it to the copy built into the image because its
  version is higher. Kodi is told to look again, and JellyELEC restarts into the new version.

- Image releases, tagged image-<build> (the build's date and time in UTC, such as
  image-202611271830), made by the "Publish an image release" workflow. Each is p3i with
  JellyELEC built in, as an image to flash and as an update tar. A system update downloads the
  tar into CoreELEC's update folder (/storage/.update); CoreELEC installs it while the box
  restarts, the same way p3i's own updates work, so nothing has to be reflashed.

Kodi's own add-on updates and p3i's updater are off in JellyELEC images, so JellyELEC checks
for both itself: once a day in the background, and whenever Check for updates is chosen in
Settings. A system update comes first when there's one, since it includes the add-on.
"""

import hashlib
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

from resources.lib import build_info
from resources.lib.kodi import ADDON_ID, ADDON_VERSION, PROFILE_PATH, log

GITHUB_REPOSITORY = "fattykidd/jellyelec"
RELEASES_URL = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases?per_page=30"
REQUEST_TIMEOUT_SECONDS = 20

ADDON_TAG_PREFIX = "v"
IMAGE_TAG_PREFIX = "image-"

ADDONS_FOLDER = "special://home/addons"
LAST_CHECK_FILE = os.path.join(PROFILE_PATH, "last_update_check")
CHECK_INTERVAL_SECONDS = 24 * 60 * 60

# Where CoreELEC looks for an update tar when it starts.
SYSTEM_UPDATE_FOLDER = "/storage/.update"
# Room to leave on /storage beyond the tar itself.
SPARE_SPACE_BYTES = 200 * 1024 * 1024
DOWNLOAD_CHUNK_BYTES = 1024 * 1024


class UpdateError(Exception):
    """Checking for or installing an update didn't work."""


class Release:
    """An add-on release on GitHub."""

    def __init__(self, version, zip_url, notes):
        self.version = version
        self.zip_url = zip_url
        self.notes = notes


class SystemUpdate:
    """An image release on GitHub: p3i with JellyELEC built in, as an update tar."""

    def __init__(self, build, p3i_release, addon_version, dovi_module, tar_name, tar_url, tar_size, checksum_url):
        self.build = build
        self.p3i_release = p3i_release
        self.addon_version = addon_version
        self.dovi_module = dovi_module
        self.tar_name = tar_name
        self.tar_url = tar_url
        self.tar_size = tar_size
        self.checksum_url = checksum_url

    @property
    def description(self):
        return f"p3i {self.p3i_release} with JellyELEC {self.addon_version}"


# Checking ---------------------------------------------------------------------------

def check():
    """Look for updates. Returns (system_update, addon_release): each None if there's nothing
    newer than what this box has. Raises UpdateError.
    """
    _remember_check()
    releases = _releases()

    system_update = _latest_system_update(releases)
    installed_build = build_info.build_id()
    if system_update and int(system_update.build) <= int(installed_build):
        system_update = None
    if system_update:
        log(f"System update available: build {installed_build} -> {system_update.build} "
            f"({system_update.description}).")

    addon_release = _latest_addon_release(releases)
    if addon_release and _version_key(addon_release.version) <= _version_key(ADDON_VERSION):
        addon_release = None
    if addon_release:
        log(f"Add-on update available: {ADDON_VERSION} -> {addon_release.version}.")

    return system_update, addon_release


def check_is_due():
    """True if a day has passed since the last check (background checks only)."""
    try:
        return time.time() - os.path.getmtime(LAST_CHECK_FILE) >= CHECK_INTERVAL_SECONDS
    except OSError:
        return True


def missing_dovi_module(update):
    """The Dolby Vision module the update needs, if this box uses Dolby Vision but doesn't have
    that module yet; else None. A box without any module isn't using Dolby Vision, so it's fine.
    """
    if not os.path.isfile(build_info.dovi_module_path()):
        return None
    if os.path.isfile(build_info.dovi_module_path(update.dovi_module)):
        return None
    return update.dovi_module


# Installing -------------------------------------------------------------------------

def install(release):
    """Download and unpack the add-on release, and have Kodi pick it up. Raises UpdateError."""
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


def download_system_update(update, report_progress=None):
    """Download the update tar into CoreELEC's update folder and check it, ready to be installed
    by a restart. report_progress(percent) is called as it downloads; if it returns False, the
    download stops and UpdateError is raised. Raises UpdateError.
    """
    os.makedirs(SYSTEM_UPDATE_FOLDER, exist_ok=True)
    free = shutil.disk_usage(SYSTEM_UPDATE_FOLDER).free
    if update.tar_size and free < update.tar_size + SPARE_SPACE_BYTES:
        raise UpdateError(f"There isn't enough free space: it needs {update.tar_size // 2**20} MB.")

    # Only one update in the folder, so CoreELEC can't install an older one left behind.
    _remove_update_tars()
    expected = _expected_checksum(update)
    target = os.path.join(SYSTEM_UPDATE_FOLDER, update.tar_name)
    partial = target + ".part"
    log(f"Downloading system update {update.tar_name}.")
    try:
        digest = _download(update.tar_url, partial, update.tar_size, report_progress)
    except UpdateError:
        _remove_quietly(partial)
        raise
    except OSError as error:
        _remove_quietly(partial)
        raise UpdateError(f"Couldn't download the update: {error}") from error

    if digest != expected:
        _remove_quietly(partial)
        raise UpdateError("The download is damaged (its checksum doesn't match). Try again.")
    os.replace(partial, target)
    log(f"System update {update.tar_name} is ready; it installs when the box restarts.")


def cancel_system_update():
    """Remove a downloaded system update that hasn't been installed yet."""
    _remove_update_tars()


# GitHub releases --------------------------------------------------------------------

def _releases():
    """Published releases, newest first."""
    releases = _get_json(RELEASES_URL) or []
    return [release for release in releases if not release.get("draft") and not release.get("prerelease")]


def _latest_addon_release(releases):
    for release in releases:
        tag = release.get("tag_name", "")
        if not tag.startswith(ADDON_TAG_PREFIX):
            continue
        version = tag[len(ADDON_TAG_PREFIX):]
        zip_url = _asset(release, f"{ADDON_ID}-{version}.zip", "browser_download_url")
        if zip_url:
            return Release(version, zip_url, release.get("body") or "")
    return None


def _latest_system_update(releases):
    image_releases = [r for r in releases if r.get("tag_name", "").startswith(IMAGE_TAG_PREFIX)]
    for release in sorted(image_releases, key=lambda r: r["tag_name"], reverse=True):
        build = release["tag_name"][len(IMAGE_TAG_PREFIX):]
        info_url = next(
            (a["browser_download_url"] for a in release.get("assets", []) if a["name"].endswith(".json")), None
        )
        tar = next((a for a in release.get("assets", []) if a["name"].endswith(".tar")), None)
        if not (build.isdigit() and info_url and tar):
            continue
        checksum_url = _asset(release, tar["name"] + ".sha256", "browser_download_url")
        info = _get_json(info_url) or {}
        return SystemUpdate(
            build=build,
            p3i_release=info.get("p3i_release", "?"),
            addon_version=info.get("addon_version", "?"),
            dovi_module=info.get("dovi_module") or build_info.DEFAULT_DOVI_MODULE,
            tar_name=tar["name"],
            tar_url=tar["browser_download_url"],
            tar_size=tar.get("size") or 0,
            checksum_url=checksum_url,
        )
    return None


def _asset(release, name, field):
    return next((asset[field] for asset in release.get("assets", []) if asset.get("name") == name), None)


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
            return None  # no releases yet
        raise UpdateError(f"GitHub answered {error.code}.") from error
    except (OSError, ValueError) as error:
        raise UpdateError(f"Couldn't reach GitHub: {error}") from error


def _expected_checksum(update):
    if not update.checksum_url:
        raise UpdateError("The release has no checksum for its update, so it can't be checked.")
    try:
        with urllib.request.urlopen(_request(update.checksum_url), timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return response.read().decode().split()[0].lower()
    except (OSError, IndexError, UnicodeDecodeError) as error:
        raise UpdateError(f"Couldn't get the update's checksum: {error}") from error


def _download(url, path, size, report_progress):
    """Save url to path, returning its SHA-256. Raises UpdateError if report_progress says stop."""
    digest = hashlib.sha256()
    done = 0
    with urllib.request.urlopen(_request(url), timeout=REQUEST_TIMEOUT_SECONDS) as response, \
            open(path, "wb") as file:
        total = size or int(response.headers.get("Content-Length") or 0)
        for chunk in iter(lambda: response.read(DOWNLOAD_CHUNK_BYTES), b""):
            file.write(chunk)
            digest.update(chunk)
            done += len(chunk)
            if report_progress and total and report_progress(done * 100 // total) is False:
                raise UpdateError("Cancelled.")
    return digest.hexdigest()


def _remove_update_tars():
    try:
        names = os.listdir(SYSTEM_UPDATE_FOLDER)
    except OSError:
        return
    for name in names:
        if name.endswith((".tar", ".tar.part")):
            _remove_quietly(os.path.join(SYSTEM_UPDATE_FOLDER, name))


def _remove_quietly(path):
    try:
        os.remove(path)
    except OSError:
        pass


def _version_key(version):
    """'0.0.43' as (0, 0, 43), so versions compare as numbers, not text."""
    return tuple(int(part) for part in version.split(".") if part.isdigit())


def _remember_check():
    os.makedirs(PROFILE_PATH, exist_ok=True)
    with open(LAST_CHECK_FILE, "w", encoding="utf-8") as file:
        file.write(str(int(time.time())))
