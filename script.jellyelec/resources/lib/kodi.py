"""Shared Kodi helpers: add-on details and logging."""

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo("id")
ADDON_NAME = ADDON.getAddonInfo("name")
ADDON_PATH = ADDON.getAddonInfo("path")
ADDON_VERSION = ADDON.getAddonInfo("version")
PROFILE_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))


def device_name():
    """The box's name as set in Kodi, shown on the server's Devices page."""
    name = xbmc.getInfoLabel("System.FriendlyName") or "CoreELEC"
    return name.replace('"', "")


def setting(setting_id):
    """Read a setting fresh, so changes apply without restarting JellyELEC."""
    return xbmcaddon.Addon().getSetting(setting_id)


def notify(message):
    """A short warning pop-up in the corner of the screen."""
    xbmcgui.Dialog().notification(ADDON_NAME, message, xbmcgui.NOTIFICATION_WARNING)


def log(message, level=xbmc.LOGINFO):
    """Write a line to kodi.log, tagged with the add-on ID."""
    xbmc.log(f"[{ADDON_ID}] {message}", level)
