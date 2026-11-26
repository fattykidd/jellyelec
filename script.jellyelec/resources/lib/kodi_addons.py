"""Installing and turning on Kodi add-ons, such as FFmpeg Direct or a weather add-on.

JellyELEC images turn off Kodi's automatic add-on updates, and with them Kodi never fetches
its add-on repositories' catalogues. So before installing, the catalogues are fetched, and
the install starts once the add-on shows up in one.
"""

import time

import xbmc

from resources.lib import jsonrpc
from resources.lib.kodi import log

CATALOGUE_TIMEOUT_SECONDS = 60
INSTALL_TIMEOUT_SECONDS = 120


def is_installed(addon_id):
    return bool(xbmc.getCondVisibility(f"System.HasAddon({addon_id})"))


def is_enabled(addon_id):
    return bool(xbmc.getCondVisibility(f"System.AddonIsEnabled({addon_id})"))


def enable(addon_id):
    xbmc.executebuiltin(f"EnableAddon({addon_id})", True)


def install(addon_id):
    """Install an add-on from Kodi's repositories. Returns True once it's installed.

    Kodi asks the user to confirm; saying no returns False.
    """
    if is_installed(addon_id):
        return True

    log(f"Fetching add-on catalogues to install {addon_id}.")
    xbmc.executebuiltin("UpdateAddonRepos")
    if not _wait_for(lambda: _in_catalogue(addon_id), CATALOGUE_TIMEOUT_SECONDS):
        log(f"{addon_id} wasn't found in any add-on repository.", xbmc.LOGWARNING)
        return False

    xbmc.executebuiltin(f"InstallAddon({addon_id})", True)
    installed = _wait_for(lambda: is_installed(addon_id), INSTALL_TIMEOUT_SECONDS)
    log(f"{addon_id} {'installed' if installed else 'was not installed'}.")
    return installed


# Helpers ----------------------------------------------------------------------------

def _in_catalogue(addon_id):
    """True once the add-on is listed in a repository's catalogue (installed or not)."""
    try:
        addons = jsonrpc.call("Addons.GetAddons", installed="all").get("addons", [])
    except jsonrpc.JsonRpcError:
        return False
    return any(addon.get("addonid") == addon_id for addon in addons)


def _wait_for(condition, timeout_seconds):
    """Wait until condition() is true. Returns False if timeout_seconds pass first."""
    monitor = xbmc.Monitor()
    started = time.monotonic()
    while not condition():
        if time.monotonic() - started > timeout_seconds or monitor.waitForAbort(1):
            return False
    return True
