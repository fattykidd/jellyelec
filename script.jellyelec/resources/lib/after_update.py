"""Finishing a p3i update on the box's first start after it.

pannal's notes for p3i T5 say an in-place update (an update tar, rather than a fresh flash)
must be followed by resetting Kodi's CoreELEC settings (Settings > System > CoreELEC) to their
defaults and restarting. JellyELEC does that by itself: when the box starts on a different p3i
release than last time, it resets those settings, sets video processor mode's Dolby Vision
settings to be made again, and restarts once. A fresh flash isn't affected: the first start
only records the release.
"""

import os

import xbmc

from resources.lib import build_info, kodi_settings, output_setup
from resources.lib.kodi import PROFILE_PATH, log

# The p3i release this box ran last time JellyELEC started.
LAST_RELEASE_FILE = os.path.join(PROFILE_PATH, "last_p3i_release")

# Kodi's CoreELEC settings (Settings > System > CoreELEC) all have IDs starting with this.
COREELEC_SETTINGS_PREFIX = "coreelec."

RESTART_DELAY_MS = 2500


def finish_if_updated(splash):
    """Finish a p3i update if this is the first start since one. Returns True if the box is
    restarting to complete it, in which case JellyELEC should go no further."""
    current = build_info.p3i_release()
    if not current:
        return False  # not a p3i system
    previous = _read_last_release()
    _write_last_release(current)
    if previous is None or previous == current:
        return False

    log(f"p3i was updated from {previous} to {current}: resetting CoreELEC's settings, as p3i requires.")
    splash.set_status("Finishing the system update…")
    kodi_settings.reset_all(COREELEC_SETTINGS_PREFIX)
    output_setup.redo_dolby_vision_settings()

    splash.set_status("Restarting to finish the system update…")
    xbmc.sleep(RESTART_DELAY_MS)
    xbmc.executebuiltin("Reboot")
    return True


def _read_last_release():
    try:
        with open(LAST_RELEASE_FILE, encoding="utf-8") as file:
            return file.read().strip() or None
    except OSError:
        return None


def _write_last_release(release):
    os.makedirs(PROFILE_PATH, exist_ok=True)
    with open(LAST_RELEASE_FILE, "w", encoding="utf-8") as file:
        file.write(release)
