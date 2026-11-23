"""Application startup and the home window."""

import xbmcaddon
import xbmcgui

ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo("path")


class HomeWindow(xbmcgui.WindowXML):
    """The JellyELEC home screen. For now it only shows the name and version."""

    def onInit(self):
        self.setProperty("version", ADDON.getAddonInfo("version"))


def run():
    window = HomeWindow("jellyelec-home.xml", ADDON_PATH, "Default", "1080i")
    window.doModal()
    del window
